import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import global_goal_ablation as experiment
from experiment import digest


class GoalProfileAblationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = experiment.ROOT / "runs/2026-10-05-context-ablation/study.json"
        cls.study = experiment.build(cls.source)

    def test_only_treatment_context_changes_and_prompt_is_frozen(self):
        self.assertEqual(self.study["arms"], experiment.ARMS)
        self.assertEqual(len(self.study["cases"]), 8)
        for case in self.study["cases"]:
            base = json.loads(case["contexts"]["code"]["state"])
            treated = json.loads(case["contexts"]["code_plus_architecture_profile"]["state"])
            self.assertNotIn("architecture_profile", base)
            profile = treated.pop("architecture_profile")
            self.assertEqual(profile["id"], "specificationcore.intent-centric")
            self.assertEqual(profile["version"], 2)
            self.assertEqual(base, treated)
        self.assertEqual(self.study["prompt_config"], json.loads(
            (experiment.ROOT / "runs/2026-10-05-independent-reference/development.json").read_text()
        )["prompt_configs"]["baseline-v1"])
        self.assertEqual(self.study["architecture_profile"]["sha256"], digest(experiment.PROFILE_PATH.read_bytes()))

    def test_preparation_is_diagnostic_and_records_directional_criteria(self):
        self.assertFalse(self.study["human_adjudicated"])
        self.assertFalse(self.study["holdout"])
        self.assertEqual(self.study["repeats"], 2)
        self.assertIn("not confirmatory", self.study["protocol"]["limits"])
        self.assertIn("mechanics_cases", self.study["protocol"]["directional_criteria"])

    def test_score_requires_complete_receipted_run_and_keeps_reference_caveat(self):
        run = {"study_sha256": digest((json.dumps(self.study, ensure_ascii=False, indent=2) + "\n").encode()),
               "prompt_sha256": digest(json.dumps(self.study["prompt_config"], ensure_ascii=False, separators=(",", ":")).encode()),
               "architecture_profile_sha256": self.study["architecture_profile"]["sha256"],
               "completed": True, "rows": []}
        for repeat in range(2):
            for arm in self.study["arms"]:
                for case in self.study["cases"]:
                    state = json.loads(case["contexts"][arm]["state"])
                    run["rows"].append({"repeat": repeat, "arm": arm, "candidate_id": case["candidate_id"],
                        "context_sha256": case["contexts"][arm]["sha256"],
                        "response": {"output": {"opportunity": {"choice": case["opportunity"]},
                                                   "concern_kind": {"choice": case["concern_kind"]}}}})
        scored = experiment.score(self.study, run)
        self.assertEqual(scored["interpretation"], "diagnostic_sensitivity_only")
        self.assertFalse(scored["human_adjudicated"])
        self.assertTrue(scored["directional_criteria"]["already_owned_cases_remain_excluded"])
        broken = copy.deepcopy(run)
        broken["rows"].pop()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            experiment.score(self.study, broken)
        broken = copy.deepcopy(run)
        broken["architecture_profile_sha256"] = "sha256:bad"
        with self.assertRaisesRegex(ValueError, "profile digest"):
            experiment.score(self.study, broken)

if __name__ == "__main__":
    unittest.main()
