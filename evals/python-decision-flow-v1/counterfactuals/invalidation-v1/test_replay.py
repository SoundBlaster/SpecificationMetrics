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
        inserted = (
            "    " + ("value = None" if kind == "overwrite" else "del value") + "\n"
        )
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
        for kind in ("overwrite", "delete"):
            with self.subTest(kind=kind):
                variant = self.variant(kind)
                result = replay.materialize_variant(
                    self.data, self.case, self.pair, variant
                )
                lines = result.splitlines(keepends=True)
                self.assertEqual(b"".join(lines[:2] + lines[3:]), self.data)

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
