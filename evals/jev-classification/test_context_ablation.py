import json
from pathlib import Path
import unittest

from context_ablation import structural_facts, score
from experiment import digest


class ContextAblationTests(unittest.TestCase):
    def test_library_binding_alias_and_shadowing(self):
        code = "RULE = FM(((PS(lambda c: c.ready), 'ready'),))"
        imports = "from specification_core import FirstMatch as FM, PredicateSpec as PS\n"
        facts = structural_facts(imports + code, code, "RULE")
        self.assertTrue(facts["direct_library_construction"])
        self.assertEqual({c["resolved_import"] for c in facts["specification_core_constructor_calls"]},
                         {"specification_core.FirstMatch", "specification_core.PredicateSpec"})
        shadowed = structural_facts(imports + "FM = another_factory\n" + code, code, "RULE")
        self.assertIsNone(shadowed["direct_library_construction"])
        ordinary = structural_facts("def FirstMatch(x): return x\n" + "RULE = FirstMatch(1)", "RULE = FirstMatch(1)", "RULE")
        self.assertIsNone(ordinary["direct_library_construction"])
        factory = "RULE = FM.with_fallback(((PS(lambda c: c.ready), 1),), 0)"
        self.assertTrue(structural_facts(imports + factory, factory, "RULE")["direct_library_construction"])
        mutated = structural_facts(imports + "FM.with_fallback = other\n" + factory, factory, "RULE")
        self.assertIsNone(mutated["direct_library_construction"])
        local = "def f(FM):\n    return FM(1)\n"
        self.assertEqual(structural_facts(imports + local, local, "f")["specification_core_constructor_calls"], [])

    def test_missing_constructor_is_not_absence_proof(self):
        facts = structural_facts("def check(x):\n    return bool(x)\n", "def check(x):\n    return bool(x)\n", "check")
        self.assertIsNone(facts["direct_library_construction"])
        self.assertIn("not proof", facts["limits"])

    def test_context_experiment_receipts_and_no_label_leakage(self):
        from validate_cases import _assert_no_label_leak
        root = Path(__file__).parent / "runs/2026-10-05-context-ablation"
        study = json.loads((root / "study.json").read_text())
        for case in study["cases"]:
            base = json.loads(case["contexts"]["code"]["state"])
            for arm, context in case["contexts"].items():
                value = json.loads(context["state"])
                _assert_no_label_leak(value)
                self.assertEqual(value["site"], base["site"])
                self.assertEqual(context["sha256"], digest(context["state"].encode()))
                for record in value.get("task_evidence", []):
                    self.assertEqual(record["excerpt_sha256"], digest(record["text"].encode()))
        positives = {c["source_candidate_id"] for c in study["cases"] if c["static_constructor_gate"]}
        self.assertEqual(positives, {"sg-018", "sg-020"})
        baseline = json.loads((Path(__file__).parent / "runs/2026-10-05-independent-reference/development.json").read_text())["prompt_configs"]["baseline-v1"]
        self.assertEqual(study["prompt_config"], baseline)
        run = json.loads((root / "run.json").read_text())
        score(study, run)
        run["rows"].pop()
        with self.assertRaises(ValueError):
            score(study, run)


if __name__ == "__main__":
    unittest.main()
