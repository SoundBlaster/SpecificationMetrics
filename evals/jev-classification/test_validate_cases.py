"""Guard against false evidence and label/split leakage in the Jev corpus."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from validate_cases import _digest, validate


class CorpusValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads((Path(__file__).parent / "corpus/cases.json").read_text())

    def test_checked_in_corpus_and_reviewer_ids(self):
        self.assertEqual(validate(self.cases), 60)
        review = json.loads((Path(__file__).parent / "corpus/review-template.json").read_text())
        self.assertEqual({r["candidate_id"] for r in review["reviews"]},
                         {json.loads(c["vars"]["candidate_json"])["candidate_id"] for c in self.cases})
        self.assertTrue(all(r["opportunity"] is None and r["concern_kind"] is None
                            for r in review["reviews"]))

    def test_previous_diagnostic_cannot_hint_model_labels(self):
        cases = deepcopy(self.cases)
        state = json.loads(cases[0]["vars"]["candidate_json"])
        state["bounded_context"]["prior_diagnostic"] = {"category": "policy"}
        cases[0]["vars"]["candidate_json"] = json.dumps(state)
        with self.assertRaisesRegex(ValueError, "evaluation-only key"):
            validate(cases)

    def test_before_and_after_cannot_cross_splits(self):
        cases = deepcopy(self.cases)
        cases[0]["metadata"]["split"] = "development"
        cases[1]["metadata"]["split"] = "holdout"
        with self.assertRaisesRegex(ValueError, "different splits"):
            validate(cases)

    def test_changed_source_is_detected_even_if_context_hash_is_updated(self):
        cases = deepcopy(self.cases)
        state = json.loads(cases[0]["vars"]["candidate_json"])
        state["site"]["code"] += "# different source\n"
        cases[0]["vars"]["candidate_json"] = json.dumps(state)
        cases[0]["metadata"]["context_sha256"] = _digest(cases[0]["vars"]["candidate_json"])
        with self.assertRaisesRegex(ValueError, "source site and model excerpt differ"):
            validate(cases)

    def test_mutable_source_revision_is_rejected(self):
        cases = deepcopy(self.cases)
        cases[0]["metadata"]["source"]["site"]["revision"] = "main"
        with self.assertRaisesRegex(ValueError, "full source commit"):
            validate(cases)

    def test_generated_hypotheses_cannot_become_gold_implicitly(self):
        cases = deepcopy(self.cases)
        cases[0]["vars"]["label_status"] = "gold"
        with self.assertRaisesRegex(ValueError, "pilot_hypothesis"):
            validate(cases)


if __name__ == "__main__":
    unittest.main()
