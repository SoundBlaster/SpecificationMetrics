"""Harness integrity checks; these microfixtures are not corpus observations."""

import copy
import difflib
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr

spec = importlib.util.spec_from_file_location(
    "counterfactual_replay", Path(__file__).with_name("replay.py")
)
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


class CounterfactualIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.data = (
            b"def f():\n    value = RULE.decide(context)\n    if value:\n        pass\n"
        )
        self.case = {
            "path": "app.py",
            "call_anchor": {"line": 2, "column": 13},
            "excerpt_lines": [2, 4],
        }
        self.pair = {
            "variable": "value",
            "branch_anchor": {"line": 3, "column": 5, "syntax_kind": "if_statement"},
        }

    def variant(self, kind):
        lines = self.data.decode().splitlines(keepends=True)
        statements = {
            "overwrite": "value = None",
            "delete": "del value",
            "comment": "# Evaluation-only preservation control.",
            "pass": "pass",
            "unrelated_literal": "_decision_flow_preservation_probe = None",
            "local_annotation": "value: object",
        }
        inserted = "    " + statements[kind] + "\n"
        changed = lines[:2] + [inserted] + lines[2:]
        excerpt = "".join(changed[1:5])
        return {
            "mutation": kind,
            "before_line": 3,
            "inserted_text": inserted,
            "modified_file_sha256": replay.real.digest("".join(changed).encode()),
            "modified_excerpt": excerpt,
            "modified_excerpt_sha256": replay.real.digest(excerpt.encode()),
            "unified_diff": "".join(
                difflib.unified_diff(
                    lines, changed, fromfile="a/app.py", tofile="b/app.py"
                )
            ),
        }

    def test_exact_insertions_preserve_every_other_byte(self):
        for kind in (
            "overwrite",
            "delete",
            "comment",
            "pass",
            "unrelated_literal",
            "local_annotation",
        ):
            with self.subTest(kind=kind):
                variant = self.variant(kind)
                result = replay.materialize_variant(
                    self.data, self.case, self.pair, variant
                )
                lines = result.splitlines(keepends=True)
                self.assertEqual(b"".join(lines[:2] + lines[3:]), self.data)

    def test_unrelated_literal_probe_must_be_fresh(self):
        for collision in (
            b"    _decision_flow_preservation_probe = 1\n",
            b"def g(_decision_flow_preservation_probe):\n    pass\n",
        ):
            with self.subTest(collision=collision):
                with self.assertRaisesRegex(ValueError, "probe collides"):
                    replay.materialize_variant(
                        self.data + collision,
                        self.case,
                        self.pair,
                        self.variant("unrelated_literal"),
                    )

    def alias_variant(self, kind):
        alias = "_decision_flow_alias_probe"
        extra, semantic = {
            "alias_copy": ([], True),
            "alias_origin_rebound": (["value = None"], True),
            "alias_rebound": ([alias + " = None"], False),
            "alias_deleted": (["del " + alias], False),
        }[kind]
        lines = self.data.decode().splitlines(keepends=True)
        inserted = "".join("    " + s + "\n" for s in [alias + " = value", *extra])
        replacement = "    if " + alias + ":\n"
        changed = (
            lines[:2] + inserted.splitlines(keepends=True) + [replacement] + lines[3:]
        )
        excerpt = "".join(changed[1:])
        return {
            "mutation": kind,
            "before_line": 3,
            "alias": alias,
            "inserted_text": inserted,
            "original_branch_line": lines[2],
            "replaced_branch_line": replacement,
            "author_expected_selected_branch_reads_origin": semantic,
            "modified_file_sha256": replay.real.digest("".join(changed).encode()),
            "modified_excerpt": excerpt,
            "modified_excerpt_sha256": replay.real.digest(excerpt.encode()),
            "unified_diff": "".join(
                difflib.unified_diff(
                    lines, changed, fromfile="a/app.py", tofile="b/app.py"
                )
            ),
        }

    def test_alias_variants_change_only_declared_prefix_and_guard_name(self):
        for kind in (
            "alias_copy",
            "alias_origin_rebound",
            "alias_rebound",
            "alias_deleted",
        ):
            with self.subTest(kind=kind):
                variant = self.alias_variant(kind)
                result = replay.materialize_variant(
                    self.data, self.case, self.pair, variant
                )
                lines = result.decode().splitlines(keepends=True)
                count = len(variant["inserted_text"].splitlines())
                restored = lines[:2] + ["    if value:\n"] + lines[3 + count :]
                self.assertEqual("".join(restored).encode(), self.data)

    def test_alias_probe_collisions_are_rejected(self):
        for collision in (
            b"    _decision_flow_alias_probe = 1\n",
            b"def g(_decision_flow_alias_probe):\n    pass\n",
        ):
            with self.subTest(collision=collision):
                with self.assertRaisesRegex(ValueError, "fresh identifier"):
                    replay.materialize_variant(
                        self.data + collision,
                        self.case,
                        self.pair,
                        self.alias_variant("alias_copy"),
                    )

    def test_alias_rewrite_cannot_change_other_guard_logic(self):
        variant = self.alias_variant("alias_copy")
        variant["replaced_branch_line"] = (
            "    if _decision_flow_alias_probe and ready:\n"
        )
        with self.assertRaisesRegex(ValueError, "only the selected guard name"):
            replay.materialize_variant(self.data, self.case, self.pair, variant)

    def test_alias_with_multiple_guard_reads_is_outside_generator_contract(self):
        data = self.data.replace(b"if value:", b"if value and value:")
        with self.assertRaisesRegex(ValueError, "one same-line guard reference"):
            replay.materialize_variant(
                data, self.case, self.pair, self.alias_variant("alias_copy")
            )

    def test_alias_semantic_label_cannot_disagree_with_operator(self):
        variant = self.alias_variant("alias_deleted")
        variant["author_expected_selected_branch_reads_origin"] = True
        with self.assertRaisesRegex(ValueError, "semantic label mismatch"):
            replay.materialize_variant(self.data, self.case, self.pair, variant)

    def report(self, status, reason, stop, branch):
        return {
            "applications": {
                "sites": [
                    {
                        "path": "app.py",
                        "line": 2,
                        "column": 13,
                        "category": "direct_application",
                        "application_id": "target",
                    }
                ]
            },
            "bindings": [
                {
                    "application_id": "target",
                    "status": status,
                    "reason": reason,
                    "stop": stop,
                    "branch": branch,
                }
            ],
        }

    def test_linked_synthetic_case_requires_the_shifted_branch_anchor(self):
        case = {**self.case, "analysis_path": "app.py", "tier": "decide_call"}
        stop = {"line": 4, "column": 5, "syntax_kind": "if_statement"}
        expected = {
            "call_category": "direct_application",
            "flow_status": "linked",
            "flow_reason": "local_straight_line_read",
        }
        report = self.report(
            "linked", "local_straight_line_read", stop, {"anchor": stop}
        )
        self.assertTrue(replay.assess_target(case, report, expected, stop)[2])
        report["bindings"][0]["branch"]["anchor"] = self.pair["branch_anchor"]
        self.assertFalse(replay.assess_target(case, report, expected, stop)[2])

    def test_negative_cannot_retain_branch_evidence(self):
        case = {**self.case, "analysis_path": "app.py", "tier": "decide_call"}
        stop = {"line": 3, "column": 5, "syntax_kind": "delete_statement"}
        expected = {
            "call_category": "direct_application",
            "flow_status": "not_linked",
            "flow_reason": "binding_deleted",
        }
        report = self.report("not_linked", "binding_deleted", stop, None)
        self.assertTrue(replay.assess_target(case, report, expected, stop)[2])
        report["bindings"][0]["branch"] = {"anchor": self.pair["branch_anchor"]}
        self.assertFalse(replay.assess_target(case, report, expected, stop)[2])

    def test_arbitrary_insertion_is_rejected_even_with_matching_hashes(self):
        variant = self.variant("overwrite")
        variant["inserted_text"] += "    unrelated = 1\n"
        with self.assertRaisesRegex(ValueError, "insertion differs"):
            replay.materialize_variant(self.data, self.case, self.pair, variant)

    def test_declared_hash_excerpt_and_diff_drift_are_rejected(self):
        for key in (
            "modified_file_sha256",
            "modified_excerpt",
            "modified_excerpt_sha256",
            "unified_diff",
        ):
            with self.subTest(key=key):
                variant = self.variant("delete")
                variant[key] = "incorrect"
                with self.assertRaisesRegex(ValueError, "provenance mismatch"):
                    replay.materialize_variant(self.data, self.case, self.pair, variant)

    def test_insertion_cannot_target_a_different_binding(self):
        pair = copy.deepcopy(self.pair)
        pair["variable"] = "other"
        with self.assertRaisesRegex(ValueError, "original binding mismatch"):
            replay.materialize_variant(
                self.data, self.case, pair, self.variant("overwrite")
            )

    def test_corpus_drift_is_rejected_before_reading_git_or_creating_output(self):
        manifest = {
            "schema": "python-decision-flow-counterfactuals/v1",
            "source_corpus_sha256": "0" * 64,
        }
        with patch.object(replay.real, "load_sources") as load:
            with self.assertRaisesRegex(ValueError, "source corpus digest mismatch"):
                replay.prepare(manifest, b"{}", Path("unused"))
            load.assert_not_called()

    def test_output_inside_source_repository_is_rejected_before_git_reads(self):
        with patch.object(
            sys,
            "argv",
            [
                "replay.py",
                "--repo",
                "unused-source",
                "--binary",
                "unused-binary",
                "--output",
                "unused-source/run",
            ],
        ):
            with (
                redirect_stderr(io.StringIO()),
                patch.object(replay, "prepare") as prepare,
            ):
                with self.assertRaises(SystemExit) as error:
                    replay.main()
                self.assertEqual(error.exception.code, 2)
                prepare.assert_not_called()


if __name__ == "__main__":
    unittest.main()
