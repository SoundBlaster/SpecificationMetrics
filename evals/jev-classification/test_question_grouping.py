import copy
import json
import unittest
from pathlib import Path
from question_grouping import canonical, digest, parse_response, validate_plan
from score_question_grouping import score


class GroupingTests(unittest.TestCase):
    def plan(self):
        return json.loads((Path(__file__).parent / "runs/2026-10-08-question-grouping/plan.json").read_text())

    def test_paired_context_and_question_invariants(self):
        plan = self.plan()
        validate_plan(plan)
        for mutate in [lambda p: p.pop(), lambda p: p.__setitem__(1, p[0])]:
            broken = copy.deepcopy(plan)
            mutate(broken)
            with self.assertRaises(ValueError):
                validate_plan(broken)
        broken = self.plan()
        broken[0]["body"]["state"]["extra"] = "changed"
        broken[0]["body_sha256"] = digest(canonical(broken[0]["body"]))
        with self.assertRaises(ValueError):
            validate_plan(broken)

    def test_full_and_partial_reports_reproduce_without_inference(self):
        for suffix in ["", "-curl", "-pinned", "-persistent"]:
            run = Path(__file__).parent / ("runs/2026-10-08-question-grouping" + suffix)
            report = score(run)
            self.assertEqual(report, json.loads((run / "summary.json").read_text()))
            if suffix != "-persistent":
                self.assertFalse(report["completed"])
                self.assertLess(report["paired"]["concern_kind"]["paired_scored_cases"], 8)
                self.assertGreater(report["summaries"]["separate"]["concern_kind"]["unscored_cases"], 0)

    def test_response_contract_and_duplicate_keys(self):
        q = {"x": {"criteria": {"a": "A", "b": "B"}}}
        body = {"model": "jev-1.13.0", "answers": {"x": {"type": "choice", "choice": "a", "probabilities": {"a": 0.8, "b": 0.2}, "confidence": 0.6}}}
        self.assertEqual(parse_response(canonical(body), q)["answers"]["x"]["choice"], "a")
        for broken in [b'{"model":"a","model":"b"}', b'{"model":NaN}', b'{}']:
            with self.assertRaises(ValueError):
                parse_response(broken, q)
        body["answers"]["x"]["probabilities"]["b"] = 0.4
        with self.assertRaises(ValueError):
            parse_response(canonical(body), q)


if __name__ == "__main__":
    unittest.main()
