#!/usr/bin/env python3
"""Replay pinned, unmodified Git sources; never import or execute corpus code."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess


def digest(data):
    return hashlib.sha256(data).hexdigest()


def relative(value):
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError(f"unsafe corpus path: {value}")
    return path


def load_sources(corpus, repos):
    """Verify every selected file and excerpt before creating run artifacts."""
    sources = {}
    for project, snapshot in corpus["snapshots"].items():
        revision = snapshot["revision"]
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError(f"full revision required: {project}")
        root = (
            relative(snapshot["import_root"])
            if snapshot["import_root"] != "."
            else PurePosixPath()
        )
        files = {}
        for item in snapshot["files"]:
            path = relative(item["path"])
            if not path.is_relative_to(root):
                raise ValueError(f"source outside import root: {path}")
            data = subprocess.check_output(
                ["git", "-C", str(repos[project]), "show", f"{revision}:{path}"]
            )
            if digest(data) != item["sha256"]:
                raise ValueError(f"source digest mismatch: {project}/{path}")
            files[str(path)] = data
        sources[project] = files
    ids = set()
    for case in corpus["cases"]:
        if case["id"] in ids:
            raise ValueError(f"duplicate case: {case['id']}")
        ids.add(case["id"])
        data = sources[case["project"]][case["path"]]
        start, end = case["excerpt_lines"]
        lines = data.decode("utf-8").splitlines(keepends=True)
        if not 1 <= start <= end <= len(lines):
            raise ValueError(f"invalid excerpt range: {case['id']}")
        excerpt = "".join(lines[start - 1 : end])
        if (
            excerpt != case["excerpt"]
            or digest(excerpt.encode()) != case["excerpt_sha256"]
        ):
            raise ValueError(f"excerpt mismatch: {case['id']}")
    return sources


def assess(case, report):
    applications = report["applications"]["sites"]
    if case["tier"] == "structural_analogue":
        start, end = case["excerpt_lines"]
        calls = [
            s
            for s in applications
            if s["path"] == case["analysis_path"] and start <= s["line"] <= end
        ]
        return {
            "call_category": "absent" if not calls else "unexpected_decide_call",
            "flow_status": "outside_api",
        }
    anchor = case["call_anchor"]
    sites = [
        s
        for s in applications
        if s["path"] == case["analysis_path"]
        and s["line"] == anchor["line"]
        and s["column"] == anchor["column"]
    ]
    if len(sites) != 1:
        return {
            "call_category": "missing_or_duplicate_call",
            "flow_status": "missing_call",
        }
    site = sites[0]
    rows = [
        r for r in report["bindings"] if r["application_id"] == site["application_id"]
    ]
    observed = {
        "call_category": site["category"],
        "flow_status": rows[0]["status"]
        if len(rows) == 1
        else "no_immediate_binding"
        if not rows
        else "duplicate_binding",
    }
    if len(rows) == 1:
        observed["flow_reason"] = rows[0]["reason"]
    return observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus", type=Path, default=Path(__file__).with_name("corpus.json")
    )
    parser.add_argument(
        "--repo", action="append", required=True, metavar="PROJECT=LOCAL_GIT_CHECKOUT"
    )
    parser.add_argument(
        "--binary", type=Path, help="omit for source/excerpt verification only"
    )
    parser.add_argument(
        "--output", type=Path, help="new artifact directory; required with --binary"
    )
    args = parser.parse_args()
    repos = {}
    for value in args.repo:
        key, path = value.split("=", 1)
        if key in repos:
            parser.error(f"duplicate --repo: {key}")
        repos[key] = Path(path).resolve()
    corpus_bytes = args.corpus.read_bytes()
    corpus = json.loads(corpus_bytes)
    if corpus["schema"] != "python-decision-flow-real-corpus/v1":
        parser.error("unsupported corpus schema")
    if set(repos) != set(corpus["snapshots"]):
        parser.error("supply exactly one --repo for every corpus project")
    if bool(args.binary) != bool(args.output):
        parser.error("--binary and --output must be supplied together")
    sources = load_sources(corpus, repos)
    if not args.binary:
        print(
            json.dumps(
                {"verified_cases": len(corpus["cases"]), "projects": len(sources)}
            )
        )
        return 0
    binary = args.binary.resolve()
    binary_hash = digest(binary.read_bytes())
    args.output.mkdir(parents=True, exist_ok=False)
    reports = {}
    measurements = {}
    for project, files in sources.items():
        snapshot = corpus["snapshots"][project]
        directory = args.output / project
        source_root = directory / "source"
        for path, data in files.items():
            destination = source_root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        import_root = source_root / snapshot["import_root"]
        paths = [
            str(PurePosixPath(p).relative_to(snapshot["import_root"])) for p in files
        ]
        scope = directory / "scope.toml"
        scope.write_text(
            "schema_version = 1\n[[source_sets]]\nrole = 'application'\npaths = "
            + json.dumps(paths)
            + "\n"
        )
        result = subprocess.run(
            [
                str(binary),
                "application-sites",
                str(import_root),
                "--profile",
                "python-decision-flow-v1",
                "--scope-manifest",
                str(scope),
            ],
            capture_output=True,
            check=True,
        )
        (directory / "flow.json").write_bytes(result.stdout)
        (directory / "stderr.txt").write_bytes(result.stderr)
        reports[project] = json.loads(result.stdout)
        if (
            reports[project]["applications"]["provisional"]
            or reports[project]["metric_effect"] != "none"
        ):
            raise ValueError(
                f"incomplete or unexpected measurement contract: {project}"
            )
        applications = reports[project]["applications"]
        measurements[project] = {
            "revision": snapshot["revision"],
            "source_digest": applications["source_digest"],
            "scope_manifest_digest": applications["scope_manifest_digest"],
            "flow_report_sha256": digest(result.stdout),
            "examined_decide_calls": applications["examined_decide_calls"],
            "examined_bindings": reports[project]["examined_bindings"],
            "linked_bindings": reports[project]["linked_bindings"],
            "unresolved_bindings": reports[project]["unresolved_bindings"],
            "not_linked_bindings": reports[project]["not_linked_bindings"],
        }
    outcomes = []
    for case in corpus["cases"]:
        observed = assess(case, reports[case["project"]])
        expected = case["expected"]
        outcomes.append(
            {
                "id": case["id"],
                "tier": case["tier"],
                "family": case["family"],
                "expected": expected,
                "observed": observed,
                "agrees": observed == expected,
            }
        )
    summary = {
        "corpus_sha256": digest(corpus_bytes),
        "analyzer_binary_sha256": binary_hash,
        "label_status": corpus["label_status"],
        "cases": len(outcomes),
        "agreement": sum(o["agrees"] for o in outcomes),
        "by_tier": dict(Counter(o["tier"] for o in outcomes)),
        "families": len({o["family"] for o in outcomes}),
        "metric_effect": "none",
        "measurements": measurements,
        "outcomes": outcomes,
    }
    (args.output / "assessment.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "outcomes"}, indent=2))
    return 0 if summary["agreement"] == summary["cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
