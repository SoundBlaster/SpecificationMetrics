"""Contract tests against the actual pinned external tools."""
import tempfile
import unittest
import json
import subprocess
import sys
from pathlib import Path

from classic_metrics import complexity, duplication


class ClassicMetricsTests(unittest.TestCase):
    def test_invalid_source_is_a_diagnostic_not_zero_complexity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "invalid.py").write_text("def broken(:\n")
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("classic_metrics.py")),
                                     str(root), "--complexity"], check=True, capture_output=True, text=True)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "partial")
            self.assertEqual(report["python_complexity"]["status"], "failed")
            self.assertNotIn("summary", report["python_complexity"])

    def test_same_named_methods_are_not_collapsed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "rules.py").write_text(
                "class One:\n    def accepts(self, x):\n        if x: return True\n        return False\n"
                "class Two:\n    def accepts(self, x):\n        if x: return True\n        return False\n"
            )
            report = complexity(root)
            functions = report["files"]["rules.py"]["cyclomatic"]
            self.assertEqual(len(functions), 2)
            self.assertEqual(report["summary"]["cc_sum"], 4)
            self.assertEqual(len(report["files"]["rules.py"]["cognitive"]), 2)
            self.assertEqual(report["versions"], {"radon": "6.0.1", "complexipy": "8.0.1"})

    def test_clone_paths_are_relative_and_snapshots_are_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = "\n".join(f"value_{n} = input_value + {n}" for n in range(20)) + "\n"
            (root / "one.py").write_text(source)
            (root / "two.py").write_text(source)
            first = duplication(root)
            self.assertGreater(first["summary"]["clone_pairs"], 0)
            self.assertEqual(first, duplication(root))
            for clone in first["clones"]:
                for side in ("firstFile", "secondFile"):
                    self.assertIn(clone[side]["path"], ("one.py", "two.py"))


if __name__ == "__main__":
    unittest.main()
