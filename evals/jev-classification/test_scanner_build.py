import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scanner_build import verified_build, verify_unchanged


class ScannerBuildTests(unittest.TestCase):
    def fixture(self, root):
        (root/"src").mkdir()
        (root/"src/main.rs").write_text("fn main() {}")
        (root/"Cargo.toml").write_text("[package]")
        (root/"Cargo.lock").write_text("lock")
        scanner = root/"target/debug/specification-metrics"
        scanner.parent.mkdir(parents=True)
        scanner.write_bytes(b"stale")
        return scanner

    def test_foreign_binary_is_rejected_before_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scanner = self.fixture(root)
            metadata = json.dumps({"target_directory": str(root/"target")}).encode()
            with patch("scanner_build.subprocess.check_output", return_value=metadata), patch("scanner_build.subprocess.run") as run:
                with self.assertRaises(ValueError):
                    verified_build(root, scanner.parent/"foreign")
                run.assert_not_called()

    def test_local_stale_binary_is_rebuilt_and_later_changes_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scanner = self.fixture(root)
            outputs = [json.dumps({"target_directory": str(root/"target")}).encode(), "a"*40, b" M src/main.rs"]
            with patch("scanner_build.subprocess.check_output", side_effect=outputs), patch("scanner_build.subprocess.run", side_effect=lambda *a, **k: scanner.write_bytes(b"fresh")) as run:
                proof = verified_build(root, scanner)
            run.assert_called_once()
            self.assertTrue(proof["build_verified"])
            self.assertTrue(proof["checkout_dirty"])
            verify_unchanged(root, scanner, proof)
            scanner.write_bytes(b"changed")
            with self.assertRaises(ValueError):
                verify_unchanged(root, scanner, proof)
            scanner.write_bytes(b"fresh")
            (root/"src/main.rs").write_text("different")
            with self.assertRaises(ValueError):
                verify_unchanged(root, scanner, proof)

    def test_source_change_during_build_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scanner = self.fixture(root)
            with patch("scanner_build.subprocess.check_output", return_value=json.dumps({"target_directory": str(root/"target")}).encode()), patch("scanner_build.subprocess.run", side_effect=lambda *a, **k: (root/"src/main.rs").write_text("changed")):
                with self.assertRaises(ValueError):
                    verified_build(root, scanner)
