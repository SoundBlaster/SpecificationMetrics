import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import prepare_specgraph_pr714_v1 as prior
import prepare_specgraph_pr714_v2 as prep
import test_specgraph_pr714_preparation_v1 as previous_tests


class PreparationTests(unittest.TestCase):
    def test_frozen_v1_failure_is_preserved_and_v2_has_no_target_overlap(self):
        self.assertEqual(prior.verify()["hosted_requests"], 0)
        counts = {}
        for case, *_ in prep.CASES:
            old = prep.load(prior.RUN / f"{case}.packet.json")["task"]["state"]
            counts[case] = sum(prep.overlaps(item["source"], old["target"]["source"])
                               for item in old["dependency_context"])
        self.assertEqual(counts, {"D01": 0, "D02": 1, "D03": 1, "D04": 0})
        with patch.dict("os.environ", {}, clear=True), patch("socket.socket.connect", side_effect=AssertionError("offline")):
            self.assertEqual(prep.verify()["target_overlap_count"], 0)

    def test_surroundings_reconstruct_the_original_parent_bytes(self):
        for case, *_ in prep.CASES:
            old = prep.load(prior.RUN / f"{case}.packet.json")
            new = prep.load(prep.RUN / f"{case}.packet.json")
            self.assertEqual(old["task"]["questions"], new["task"]["questions"])
            self.assertEqual(old["semantic_instructions"], new["semantic_instructions"])
            old_state, new_state = old["task"]["state"], new["task"]["state"]
            self.assertEqual(old_state["target"], new_state["target"])
            target = old_state["target"]["source"]
            for entry in old_state["dependency_context"]:
                source = entry["source"]
                pieces = prep.surrounding(source, target)
                if prep.overlaps(source, target):
                    self.assertEqual(pieces[0]["code"] + target["code"] + pieces[1]["code"], source["code"])
                for piece in pieces:
                    self.assertFalse(prep.overlaps(piece, target))
                    self.assertEqual(piece["excerpt_sha256"], "sha256:" + prep.sha(piece["code"].encode()))
            self.assertEqual(prep.load(prep.RUN / f"{case}.context.json"), prep.context_for(new))
            self.assertEqual(prep.load(prep.RUN / f"{case}.context.json")["assessment"]["status"], "not_run")
            if case in ("D01", "D04"):
                self.assertEqual((prep.RUN / f"{case}.packet.json").read_bytes(),
                                 (prior.RUN / f"{case}.packet.json").read_bytes())
            else:
                self.assertNotEqual(prep.context_for(new)["expected"]["evidence_sha256"],
                                    prep.context_for(old)["expected"]["evidence_sha256"])

    def test_subtraction_handles_exact_containment_partial_and_foreign_sources(self):
        def source(start, end, path="x.py", revision="a"):
            code = "".join(f"line {i}\n" for i in range(start, end + 1))
            return dict(path=path, revision=revision, start_line=start, end_line=end,
                        symbol="example", code=code, excerpt_sha256="sha256:" + prep.sha(code.encode()))
        target = source(3, 5)
        for start, end, spans in ((1, 7, [(1, 2), (6, 7)]), (3, 5, []), (4, 4, []),
                                  (1, 4, [(1, 2)]), (4, 8, [(6, 8)]), (6, 8, [(6, 8)])):
            pieces = prep.surrounding(source(start, end), target)
            self.assertEqual([(p["start_line"], p["end_line"]) for p in pieces], spans)
        for original in (source(3, 5, path="other.py"), source(3, 5, revision="b")):
            self.assertEqual(prep.surrounding(original, target), [original])

    def test_rebound_parent_reintroduction_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            bundle = Path(td) / "bundle"
            shutil.copytree(prep.RUN, bundle)
            path = bundle / "D02.packet.json"
            packet = prep.load(path)
            old = prep.load(prior.RUN / path.name)
            parent = next(e for e in old["task"]["state"]["dependency_context"]
                          if prep.overlaps(e["source"], old["task"]["state"]["target"]["source"]))
            packet["task"]["state"]["dependency_context"].append(copy.deepcopy(parent))
            path.write_text(prep.encoded(packet) + "\n")
            receipt = prep.load(bundle / "preparation-receipt.json")
            receipt["files_sha256"][path.name] = prep.sha(path.read_bytes())
            (bundle / "preparation-receipt.json").write_text(prep.encoded(receipt) + "\n")
            with self.assertRaisesRegex(ValueError, "dependency fragment overlaps target"):
                prep.verify(bundle)


class BridgePreparationTests(previous_tests.BridgePreparationTests):
    def setUp(self):
        # Reuse both established SDK profiles and synthetic routing checks with
        # the corrected packets; the frozen v1 module's code is unchanged.
        replacement = patch.object(prior, "RUN", prep.RUN)
        replacement.start()
        self.addCleanup(replacement.stop)


if __name__ == "__main__":
    unittest.main()
