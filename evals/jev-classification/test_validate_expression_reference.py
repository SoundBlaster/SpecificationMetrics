import copy
import json
from pathlib import Path
import unittest

from validate_expression_reference import validate
from question_grouping import digest


RUN = Path(__file__).parent / "runs/2026-10-12-expression-reference"


class ExpressionReferenceTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads((RUN / "reference-packet.json").read_text())
        self.reference = json.loads((RUN / "independent-annotations.json").read_text())

    def test_all_eight_annotations_match_task_labels_and_source_quotes(self):
        result = validate(self.packet, self.reference)
        self.assertEqual(result["annotated_cases"], 8)
        self.assertEqual(result["authority"], "independent_model_reference_not_human_gold")

    def test_missing_duplicate_stale_or_invalid_labels_are_rejected(self):
        mutations = [lambda r: r["annotations"].pop(),
                     lambda r: r["annotations"].__setitem__(1, copy.deepcopy(r["annotations"][0])),
                     lambda r: r.update(packet_sha256="stale"),
                     lambda r: r["annotations"][0].update(state_sha256="stale"),
                     lambda r: r["annotations"][0].update(opportunity="policy"),
                     lambda r: r.update(authority="human_gold")]
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                changed = copy.deepcopy(self.reference)
                mutate(changed)
                validate(self.packet, changed)

    def test_missing_or_invented_evidence_is_rejected(self):
        mutations = [lambda r: r["annotations"][0].update(evidence=[]),
                     lambda r: r["annotations"][0]["evidence"][0].update(quote="not present in supplied code"),
                     lambda r: r["annotations"][0]["evidence"][0].update(location="outside-task"),
                     lambda r: r["annotations"][0]["evidence"][0].update(reason="")]
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                changed = copy.deepcopy(self.reference)
                mutate(changed)
                validate(self.packet, changed)

    def test_review_preserves_original_uncertainties_and_does_not_claim_provider_accuracy(self):
        review = json.loads((RUN / "reference-review.json").read_text())
        self.assertEqual(review["reference_sha256"], digest((RUN / "independent-annotations.json").read_bytes()))
        self.assertEqual(review["proposals_sha256"], digest((RUN / "annotation-proposals.json").read_bytes()))
        self.assertEqual(review["validator_sha256"], digest(Path(__file__).with_name("validate_expression_reference.py").read_bytes()))
        self.assertEqual(review["validation"], validate(self.packet, self.reference))
        self.assertEqual(review["jev_luna_requests"], 0)
        self.assertEqual(review["label_overrides"], [])
        originals = {r["case_id"]: r["uncertainties"] for r in self.reference["annotations"] if r["uncertainties"]}
        reviewed = {r["case_id"]: r["original_uncertainties"] for r in review["uncertainty_review"]}
        self.assertEqual(originals, reviewed)
        proposals = {r["case_id"]: r for r in json.loads((RUN / "annotation-proposals.json").read_text())["annotations"]}
        for axis in ["opportunity", "concern_kind"]:
            matched = sum(r[axis] == proposals[r["case_id"]][axis] for r in self.reference["annotations"])
            self.assertEqual(review["proposal_agreement"][axis], {"matched": matched, "total": 8})


if __name__ == "__main__":
    unittest.main()
