import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "flow_replay", Path(__file__).with_name("replay.py")
)
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


class ReplayContractTests(unittest.TestCase):
    def test_missing_call_cannot_pass_as_no_binding(self):
        case = {
            "tier": "decide_call",
            "analysis_path": "app.py",
            "call_anchor": {"line": 3, "column": 5},
        }
        result = replay.assess(case, {"applications": {"sites": []}, "bindings": []})
        self.assertEqual(result["flow_status"], "missing_call")

    def test_binding_is_joined_by_application_identity(self):
        case = {
            "tier": "decide_call",
            "analysis_path": "app.py",
            "call_anchor": {"line": 3, "column": 5},
        }
        report = {
            "applications": {
                "sites": [
                    {
                        "path": "app.py",
                        "line": 3,
                        "column": 5,
                        "application_id": "first",
                        "category": "direct_application",
                    }
                ]
            },
            "bindings": [
                {
                    "application_id": "other",
                    "status": "linked",
                    "reason": "local_straight_line_read",
                }
            ],
        }
        self.assertEqual(
            replay.assess(case, report)["flow_status"], "no_immediate_binding"
        )
        report["bindings"][0]["application_id"] = "first"
        self.assertEqual(replay.assess(case, report)["flow_status"], "linked")

    def test_analogue_does_not_become_a_successful_native_link(self):
        case = {
            "tier": "structural_analogue",
            "analysis_path": "app.py",
            "excerpt_lines": [4, 6],
        }
        report = {"applications": {"sites": [{"path": "app.py", "line": 9}]}}
        self.assertEqual(
            replay.assess(case, report),
            {"call_category": "absent", "flow_status": "outside_api"},
        )
        report["applications"]["sites"][0]["line"] = 5
        self.assertEqual(
            replay.assess(case, report)["call_category"], "unexpected_decide_call"
        )

    def test_excerpt_drift_fails_before_artifact_creation(self):
        data = b"original\n"
        corpus = {
            "snapshots": {
                "demo": {
                    "revision": "a" * 40,
                    "import_root": ".",
                    "files": [{"path": "app.py", "sha256": replay.digest(data)}],
                }
            },
            "cases": [
                {
                    "id": "one",
                    "project": "demo",
                    "path": "app.py",
                    "excerpt_lines": [1, 1],
                    "excerpt": "changed\n",
                    "excerpt_sha256": replay.digest(b"changed\n"),
                }
            ],
        }
        from unittest.mock import patch

        with patch.object(replay.subprocess, "check_output", return_value=data):
            with self.assertRaisesRegex(ValueError, "excerpt mismatch"):
                replay.load_sources(corpus, {"demo": Path("unused")})
            changed = copy.deepcopy(corpus)
            changed["snapshots"]["demo"]["files"][0]["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "source digest mismatch"):
                replay.load_sources(changed, {"demo": Path("unused")})

    def test_parent_paths_are_rejected(self):
        for value in ("/tmp/escape", "../escape", "x/../escape"):
            with self.assertRaises(ValueError):
                replay.relative(value)


if __name__ == "__main__":
    unittest.main()
