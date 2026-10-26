import itertools
import json
from pathlib import Path
import unittest

from model import Machine, Operation, analyze


ROOT = Path(__file__).resolve().parents[2]
AT = {"line": 3, "column": 5, "syntax_kind": "expression_statement"}


class ReferenceTests(unittest.TestCase):
    def run_code(self, tail, projection="raw", **kwargs):
        origin = "d = RULE.decide(ctx)" + (
            "" if projection == "raw" else "." + projection
        )
        code = (
            "def fixture(ctx):\n    "
            + origin
            + "\n"
            + "".join("    " + s + "\n" for s in tail)
        )
        return analyze(
            code,
            {"line": 2, "column": 9},
            projection,
            origin_id="fixture-origin",
            origin_proven=True,
            **kwargs,
        )

    def test_frozen_matrix(self):
        matrix = json.loads((ROOT / "docs/local-alias-flow-cases.json").read_bytes())
        self.assertEqual(len(matrix["unit_cases"]), 47)
        for case in matrix["unit_cases"]:
            with self.subTest(case=case["id"]):
                actual = analyze(
                    case["code"],
                    case["target_origin"],
                    case["origin_projection"],
                    origin_id=case["id"],
                    origin_proven=True,
                )
                self.assertEqual(actual["outcome"], case["expected"])

    def test_copy_noninterference_over_all_two_name_states(self):
        # 12 abstract maps x 4 copy operations; no Python programs are executed.
        for d_state, a_state in itertools.product(
            ("origin", "other", "deleted"), (None, "origin", "other", "deleted")
        ):
            initial = {"d": d_state, **({"a": a_state} if a_state is not None else {})}
            for target, source in itertools.product(("d", "a"), repeat=2):
                with self.subTest(initial=initial, target=target, source=source):
                    machine = Machine("d", "raw", "abstract-origin")
                    machine.states = dict(initial)
                    machine.step(Operation("copy", AT, target=target, source=source))
                    if source not in initial or initial[source] == "deleted":
                        self.assertEqual(machine.states, initial)
                        self.assertEqual(machine.events, [])
                        self.assertEqual(machine.outcome["status"], "unresolved")
                    else:
                        self.assertEqual(machine.states[target], initial[source])
                        for name in initial.keys() - {target}:
                            self.assertEqual(machine.states[name], initial[name])
                        self.assertIsNone(machine.outcome)
                        self.assertEqual(len(machine.events), 1)

    def test_rebind_and_delete_noninterference(self):
        for d_state, a_state in itertools.product(
            ("origin", "other", "deleted"), (None, "origin", "other", "deleted")
        ):
            initial = {"d": d_state, **({"a": a_state} if a_state is not None else {})}
            for kind, target in itertools.product(("literal", "delete"), ("d", "a")):
                machine = Machine("d", "raw", "abstract-origin")
                machine.states = dict(initial)
                machine.step(Operation(kind, AT, target=target))
                for name in initial.keys() - {target}:
                    self.assertEqual(machine.states[name], initial[name])
                if kind == "delete" and initial.get(target) in (None, "deleted"):
                    self.assertEqual(machine.states, initial)
                    self.assertEqual(machine.events, [])
                    self.assertEqual(
                        machine.outcome["reason"], "deletion_state_unproven"
                    )
                elif target in initial:
                    self.assertEqual(
                        machine.states[target],
                        "other" if kind == "literal" else "deleted",
                    )
                else:
                    self.assertEqual(machine.states, initial)

    def test_guard_partition_over_all_two_name_states(self):
        expected = {
            "origin": "linked",
            "other": "not_linked",
            "deleted": "not_linked",
            None: "unresolved",
        }
        for d_state, a_state in itertools.product(
            ("origin", "other", "deleted"), (None, "origin", "other", "deleted")
        ):
            for target in ("d", "a"):
                machine = Machine("d", "raw", "abstract-origin")
                machine.states = {
                    "d": d_state,
                    **({"a": a_state} if a_state is not None else {}),
                }
                result = machine.step(
                    Operation("guard", AT, target=target, projection="value")
                )
                self.assertEqual(result["status"], expected[machine.states.get(target)])

    def test_comments_count_at_the_statement_limit(self):
        limits = {"max_tracked_names": 8, "max_following_named_sibling_nodes": 2}
        exact = self.run_code(["# comment", "if d.value:", "    pass"], limits=limits)
        overflow = self.run_code(
            ["# one", "# two", "if d.value:", "    pass"], limits=limits
        )
        self.assertEqual(exact["outcome"]["status"], "linked")
        self.assertEqual(overflow["outcome"]["reason"], "statement_limit")
        self.assertEqual(overflow["evidence"]["events"], [])

    def test_trailing_comments_are_not_lost_at_scope_end(self):
        limits = {"max_tracked_names": 8, "max_following_named_sibling_nodes": 1}
        result = self.run_code(["# one", "# two"], limits=limits)
        self.assertEqual(result["outcome"]["reason"], "statement_limit")

    def test_inline_comments_after_origin_and_assignment_count(self):
        limits = {"max_tracked_names": 8, "max_following_named_sibling_nodes": 2}
        result = self.run_code(
            ["a = d  # inline sibling", "if a.value:", "    pass"], limits=limits
        )
        self.assertEqual(result["outcome"]["reason"], "statement_limit")
        code = "def f(ctx):\n    d = RULE.decide(ctx)  # sibling after origin\n    if d.value:\n        pass\n"
        result = analyze(
            code,
            {"line": 2, "column": 9},
            "raw",
            origin_id="o",
            origin_proven=True,
            limits={"max_tracked_names": 8, "max_following_named_sibling_nodes": 1},
        )
        self.assertEqual(result["outcome"]["reason"], "statement_limit")

    def test_deleted_source_precedes_name_limit_and_rejection_has_no_event(self):
        machine = Machine(
            "d",
            "raw",
            "o",
            {"max_tracked_names": 1, "max_following_named_sibling_nodes": 64},
        )
        machine.step(Operation("delete", AT, target="d"))
        machine.step(Operation("copy", AT, target="a", source="d"))
        self.assertEqual(machine.outcome["reason"], "alias_copy_source_deleted")
        self.assertEqual(len(machine.events), 1)
        self.assertNotIn("a", machine.states)

    def test_projection_cannot_be_bypassed_by_abstract_guard(self):
        machine = Machine("d", "raw", "o")
        machine.step(Operation("guard", AT, target="d"))
        self.assertEqual(machine.outcome["status"], "unresolved")

    def test_no_enum_recognition_by_capitalization(self):
        result = self.run_code(["a = d", "if a.value == Disposition.ADD:", "    pass"])
        self.assertEqual(result["outcome"]["status"], "unresolved")
        supplied = self.run_code(
            ["a = d", "if a.value == Disposition.ADD:", "    pass"],
            enum_facts={("Disposition", "ADD")},
        )
        self.assertEqual(supplied["outcome"]["status"], "linked")

    def test_scope_directive_outside_loop_and_nested_scope_separation(self):
        code = "def f(ctx):\n    global d\n    for x in []:\n        d = RULE.decide(ctx)\n        if d.value:\n            pass\n"
        result = analyze(
            code, {"line": 4, "column": 13}, "raw", origin_id="o", origin_proven=True
        )
        self.assertEqual(result["outcome"]["reason"], "global_or_nonlocal_scope")
        code = "def f(ctx):\n    def g():\n        global d\n    d = RULE.decide(ctx)\n    if d.value:\n        pass\n"
        result = analyze(
            code, {"line": 4, "column": 9}, "raw", origin_id="o", origin_proven=True
        )
        self.assertEqual(result["outcome"]["status"], "linked")

    def test_literal_and_copy_syntax_does_not_expand_silently(self):
        for statement in (
            "a = (d)",
            "a = (None)",
            "a = f'{d}'",
            "a = [d]",
            "a: object = d",
        ):
            with self.subTest(statement=statement):
                result = self.run_code([statement, "if d.value:", "    pass"])
                self.assertEqual(result["outcome"]["status"], "unresolved")

    def test_explicit_origin_precondition_and_anchor_checks(self):
        code = "def f(ctx):\n    d = RULE.decide(ctx)\n    if d.value:\n        pass\n"
        result = analyze(
            code, {"line": 2, "column": 9}, "raw", origin_id="o", origin_proven=False
        )
        self.assertEqual(result["outcome"]["reason"], "firstmatch_binding_not_proven")
        with self.assertRaisesRegex(ValueError, "anchor unavailable"):
            analyze(
                code, {"line": 9, "column": 9}, "raw", origin_id="o", origin_proven=True
            )


if __name__ == "__main__":
    unittest.main()
