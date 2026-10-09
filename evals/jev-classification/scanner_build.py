"""Build and bind the executed debug scanner to this checkout's Rust inputs."""
import json
from pathlib import Path
import subprocess

from question_grouping import digest


def source_digests(root):
    paths = sorted((root/"src").rglob("*.rs")) + [root/"Cargo.toml", root/"Cargo.lock"]
    if (root/"build.rs").exists():
        paths.append(root/"build.rs")
    return {str(p.relative_to(root)): digest(p.read_bytes()) for p in paths}


def verified_build(root, scanner):
    root = root.resolve()
    metadata = json.loads(subprocess.check_output(
        ["cargo", "metadata", "--locked", "--offline", "--no-deps", "--format-version", "1"], cwd=root))
    expected = Path(metadata["target_directory"])/"debug/specification-metrics"
    if scanner.resolve() != expected.resolve():
        raise ValueError("Scanner must be this checkout's Cargo debug binary; foreign paths are not allowed")
    before = source_digests(root)
    command = ["cargo", "build", "--locked", "--manifest-path", str(root/"Cargo.toml")]
    subprocess.run(command, cwd=root, check=True)
    if before != source_digests(root):
        raise ValueError("Rust sources changed during scanner build")
    return {"build_verified": True, "build_command": ["cargo", "build", "--locked", "--manifest-path", "Cargo.toml"],
            "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
            "checkout_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root)),
            "source_digests": before, "binary_sha256": digest(scanner.read_bytes())}


def verify_unchanged(root, scanner, provenance):
    if source_digests(root) != provenance["source_digests"] or digest(scanner.read_bytes()) != provenance["binary_sha256"]:
        raise ValueError("Scanner binary or Rust sources changed during audit")
