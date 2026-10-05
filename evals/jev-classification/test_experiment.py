import copy
import json
import unittest

from experiment import freeze, metrics, prepare, rows_from_run


class ExperimentTests(unittest.TestCase):
    def fixtures(self):
        cases, reviews = [], []
        for i in range(8):
            context = json.dumps({"candidate_id": str(i), "site": {"code": "if allowed: pass"}})
            cases.append({"vars": {"candidate_json": context, "expected_opportunity": "excluded"},
                          "metadata": {"family_id": str(i // 2)}})
        _, mapping = prepare(cases)
        for opaque in mapping:
            reviews.append({"candidate_id": opaque, "opportunity": "eligible",
                            "concern_kind": "policy", "rationale": "An admission decision"})
        annotations = {"reference_kind": "independent_model_annotation", "reviewer_id": "fixture",
                       "saw_proposed_labels": False, "saw_jev_outputs": False, "reviews": reviews}
        return cases, annotations, mapping

    def test_families_and_provisional_labels(self):
        cases, annotations, mapping = self.fixtures()
        manifest = freeze(cases, annotations, mapping)
        splits = {}
        for case in manifest["cases"]:
            self.assertEqual(case["opportunity"], "eligible")
            splits.setdefault(case["family_id"], set()).add(case["split"])
            self.assertEqual(json.loads(case["context"])["candidate_id"], case["candidate_id"])
        self.assertTrue(all(len(s) == 1 for s in splits.values()))
        self.assertFalse(manifest["human_adjudicated"])
        cases[0]["vars"]["expected_opportunity"] = "needs_review"
        self.assertEqual(manifest, freeze(cases, annotations, mapping))

    def test_stale_mapping_rejected_when_candidate_context_changes(self):
        cases, annotations, mapping = self.fixtures()
        cases[0]["vars"]["candidate_json"] = cases[0]["vars"]["candidate_json"].replace(
            "if allowed", "if allowed and approved")
        with self.assertRaisesRegex(ValueError, "mapping context identity"):
            freeze(cases, annotations, mapping)

    def test_packet_does_not_contain_proposals_or_split_metadata(self):
        cases, _, _ = self.fixtures()
        packet, mapping = prepare(cases)
        text = json.dumps(packet)
        self.assertNotIn("expected_opportunity", text)
        self.assertNotIn("family_id", text)
        self.assertEqual(len(mapping), 8)

    def test_committed_reference_and_compact_receipts(self):
        from pathlib import Path
        root = Path(__file__).parent
        cases = json.loads((root / "corpus/cases.json").read_text())
        _, mapping = prepare(cases)
        manifest = freeze(cases, json.loads((root / "corpus/annotations.model-v1.json").read_text()), mapping)
        frozen = json.loads((root / "corpus/experiment-v1.json").read_text())
        slim = {**manifest, "cases": [{k: v for k, v in c.items() if k != "context"} for c in manifest["cases"]]}
        self.assertEqual(slim, frozen)
        for phase in ("development", "holdout"):
            run = json.loads((root / "runs/2026-10-05-independent-reference" / f"{phase}.json").read_text())
            rows_from_run(run, manifest)

    def test_invalid_annotation_and_blindness(self):
        cases, annotations, mapping = self.fixtures()
        for change in ("duplicate", "missing", "leak", "invalid"):
            a = copy.deepcopy(annotations)
            if change == "duplicate":
                a["reviews"].append(a["reviews"][0])
            elif change == "missing":
                a["reviews"].pop()
            elif change == "leak":
                a["saw_proposed_labels"] = True
            else:
                a["reviews"][0]["opportunity"] = "policy"
            with self.assertRaises(ValueError):
                freeze(cases, a, mapping)

    def test_abstention_cannot_win_and_errors_remain(self):
        m = metrics([("eligible", "needs_review"), ("eligible", None), ("excluded", "excluded")], "opportunity")
        self.assertEqual(m["per_class"]["eligible"]["recall"], 0)
        self.assertEqual(m["provider_or_contract_errors"], 1)
        self.assertAlmostEqual(m["abstention_rate"], 1 / 3)
        self.assertAlmostEqual(m["scored_abstention_rate"], 1 / 2)
        self.assertEqual(m["scored_cases"], 2)
        failed_abstention_reference = metrics([("needs_review", None)], "opportunity")
        self.assertEqual(failed_abstention_reference["provider_or_contract_errors"], 1)
        self.assertEqual(failed_abstention_reference["per_class"]["needs_review"]["support"], 0)
        self.assertIsNone(failed_abstention_reference["macro_f1"])
        self.assertEqual(metrics([("eligible", "excluded")], "opportunity")["false_exclusions"], 1)

    def test_partial_runs_and_changed_context_rejected(self):
        manifest = freeze(*self.fixtures())
        c = manifest["cases"][0]
        row = {"vars": {"candidate_json": c["context"]}, "provider": {"id": "baseline-v1"},
               "response": {"output": {"opportunity": {"choice": "eligible"}, "concern_kind": {"choice": "policy"}}}}
        run = {"phase": c["split"], "candidate_ids": [c["candidate_id"]], "variant_ids": ["baseline-v1"], "results": {"results": [row]}}
        rows_from_run(run, manifest)
        bad = copy.deepcopy(run)
        bad["results"]["results"] = []
        with self.assertRaises(ValueError):
            rows_from_run(bad, manifest)
        bad = copy.deepcopy(run)
        bad["phase"] = "holdout" if c["split"] == "development" else "development"
        with self.assertRaises(ValueError):
            rows_from_run(bad, manifest)
        bad = copy.deepcopy(run)
        bad["results"]["results"][0]["vars"]["candidate_json"] += " "
        with self.assertRaises(ValueError):
            rows_from_run(bad, manifest)


if __name__ == "__main__":
    unittest.main()
