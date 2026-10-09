import copy
import json
from pathlib import Path
import sys
import unittest

from experiment import digest
from ownership_gate import construction_evidence, route
from score_rubric_alignment import score


def fixture(prefix="from specification_core import FirstMatch as FM\n", statement="DECISION = FM(())\n"):
    raw = (prefix + statement).encode()
    return raw, {"revision": "a" * 40, "path": "example.py", "symbol": "DECISION",
                 "start_line": len(prefix.splitlines()) + 1, "end_line": len((prefix + statement).splitlines()),
                 "file_sha256": digest(raw), "excerpt_sha256": digest(statement.encode()), "code": statement}


class ConstructionGateTests(unittest.TestCase):
    def test_resolved_alias_and_fallback(self):
        for call in ["FM(())", "FM.with_fallback((), 1)"]:
            raw, site = fixture(statement="DECISION = " + call + "\n")
            result = construction_evidence(raw, site)
            self.assertEqual(result["status"], "direct_specification_construction")
            self.assertTrue(result["resolved_constructor"].startswith("specification_core.FirstMatch"))

    def test_unknown_is_not_excluded(self):
        prefixes = ["from elsewhere import FirstMatch as FM\n", "from .specification_core import FirstMatch as FM\n",
                    "from specification_core import FirstMatch as FM\nFM = other\n",
                    "from specification_core import FirstMatch as FM\ndel FM\n",
                    "from specification_core import FirstMatch as FM\nFM.with_fallback = other\n",
                    "from specification_core import FirstMatch as FM\nfrom elsewhere import *\n",
                    "from specification_core import FirstMatch as FM\nexec(code)\n",
                    "from specification_core import FirstMatch as FM\ntry:\n    pass\nexcept Exception as FM:\n    pass\n",
                    "from specification_core import FirstMatch as FM\ndef FM(): pass\n",
                    "import specification_core as sc\n"]
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                raw, site = fixture(prefix)
                evidence = construction_evidence(raw, site)
                self.assertEqual(evidence["status"], "unknown")
                calls = []
                self.assertEqual(route(evidence, lambda: calls.append(1) or "needs_review")["opportunity"], "needs_review")
                self.assertEqual(calls, [1])

    @unittest.skipIf(sys.version_info < (3, 10), "Pattern matching requires Python 3.10")
    def test_pattern_capture_invalidates_binding(self):
        raw, site = fixture("from specification_core import FirstMatch as FM\nmatch value:\n    case FM:\n        pass\n")
        self.assertEqual(construction_evidence(raw, site)["status"], "unknown")

    def test_function_body_and_neighbor_constructor_do_not_prove_ownership(self):
        for statement in ["def DECISION(x):\n    return FM(x)\n", "DECISION = other(FM(()))\n"]:
            raw, site = fixture(statement=statement)
            self.assertEqual(construction_evidence(raw, site)["status"], "unknown")

    def test_owned_site_bypasses_provider(self):
        raw, site = fixture()
        def forbidden():
            self.fail("Owned construction reached semantic provider")
        result = route(construction_evidence(raw, site), forbidden)
        self.assertEqual(result["opportunity"], "excluded")
        self.assertNotIn("concern_kind", result)

    def test_stale_or_misbound_source_fails(self):
        raw, site = fixture()
        with self.assertRaises(ValueError):
            construction_evidence(raw + b"# changed\n", site)
        for changes in [{"code": "DECISION = other(())\n"}, {"start_line": 1}, {"end_line": 999}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                construction_evidence(raw, {**site, **changes})
        self.assertEqual(construction_evidence(raw, {**site, "symbol": "NEIGHBOR"})["status"], "unknown")

    def test_unknown_status_rejected(self):
        with self.assertRaises(ValueError):
            route({"status": "unowned"}, lambda: "excluded")

    def test_frozen_replay_preserves_raw_predictions_and_unknowns(self):
        path = Path(__file__).parent/"runs/2026-10-10-ownership-gate/report.json"
        if not path.exists():
            self.fail("Missing frozen ownership replay")
        report = json.loads(path.read_text())
        self.assertEqual(report["new_inference_requests"], 0)
        self.assertEqual(len(report["cases"]), 8)
        original = score(path.parent.parent/"2026-10-10-rubric-alignment")
        self.assertEqual([(c["candidate_id"], c["reference"], c["predictions"]) for c in report["cases"]],
                         [(c["candidate_id"], c["reference"], c["predictions"]) for c in original["cases"]])
        for case in report["cases"]:
            expected = copy.deepcopy(case["predictions"])
            if case["evidence"]["status"] == "direct_specification_construction":
                for arms in expected.values():
                    for prediction in arms.values():
                        prediction["opportunity"] = "excluded"
            self.assertEqual(expected, case["routed_predictions"])


if __name__ == "__main__":
    unittest.main()
