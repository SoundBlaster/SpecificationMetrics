#!/usr/bin/env python3
"""Replay explicit counterfactuals on isolated copies of pinned Git blobs."""

import argparse
import ast
import difflib
import importlib.util
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("real_flow_replay", ROOT / "replay.py")
real = importlib.util.module_from_spec(spec)
spec.loader.exec_module(real)


def identifier_present(tree, name):
    return any(
        isinstance(node, ast.Name)
        and node.id == name
        or isinstance(node, ast.arg)
        and node.arg == name
        for node in ast.walk(tree)
    )


def alias_change(lines, tree, branch, variable, variant):
    """Insert a fresh local alias and rewrite only one original guard name."""
    alias = "_decision_flow_alias_probe"
    if variant["alias"] != alias or identifier_present(tree, alias):
        raise ValueError("alias probe must be the declared fresh identifier")
    names = [
        n for n in ast.walk(branch.test) if isinstance(n, ast.Name) and n.id == variable
    ]
    if (
        len(names) != 1
        or names[0].lineno != branch.lineno
        or names[0].end_lineno != branch.lineno
    ):
        raise ValueError("alias rewrite requires one same-line guard reference")
    extras = {
        "alias_copy": ([], True),
        "alias_origin_rebound": ([f"{variable} = None"], True),
        "alias_rebound": ([f"{alias} = None"], False),
        "alias_deleted": ([f"del {alias}"], False),
    }
    if variant["mutation"] not in extras:
        raise ValueError("unsupported alias mutation")
    extra, semantic = extras[variant["mutation"]]
    if variant["author_expected_selected_branch_reads_origin"] is not semantic:
        raise ValueError("alias semantic label mismatch")
    original = lines[branch.lineno - 1]
    raw = original.encode()
    reference = names[0]
    replacement = (
        raw[: reference.col_offset] + alias.encode() + raw[reference.end_col_offset :]
    ).decode()
    if (
        variant["original_branch_line"] != original
        or variant["replaced_branch_line"] != replacement
    ):
        raise ValueError("alias rewrite must change only the selected guard name")
    indent = original[: branch.col_offset]
    inserted = "".join(indent + s + "\n" for s in [f"{alias} = {variable}", *extra])
    return inserted, replacement


def materialize_variant(data, case, pair, variant):
    """Permit declared insertions and a bounded optional alias guard rewrite."""
    lines = data.decode("utf-8").splitlines(keepends=True)
    line = pair["branch_anchor"]["line"]
    branch = next(
        (
            n
            for n in ast.walk(ast.parse(data))
            if isinstance(n, ast.If) and n.lineno == line
        ),
        None,
    )
    if branch is None or branch.col_offset + 1 != pair["branch_anchor"]["column"]:
        raise ValueError("original branch anchor mismatch")
    tree = ast.parse(data)
    parents = {
        child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)
    }
    anchor = case["call_anchor"]
    call = next(
        (
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and (n.lineno, n.col_offset + 1) == (anchor["line"], anchor["column"])
        ),
        None,
    )
    owner = call
    while owner is not None and not isinstance(owner, ast.Assign):
        owner = parents.get(owner)
    if (
        owner is None
        or len(owner.targets) != 1
        or not isinstance(owner.targets[0], ast.Name)
        or owner.targets[0].id != pair["variable"]
        or owner.end_lineno >= line
    ):
        raise ValueError("original binding mismatch")
    siblings = parents[owner].body
    if siblings[siblings.index(owner) + 1].lineno != line:
        raise ValueError("branch is not the next original statement")
    indent = lines[line - 1][: branch.col_offset]
    variable = pair["variable"]
    probe = "_decision_flow_preservation_probe"
    statements = {
        "overwrite": f"{variable} = None",
        "delete": f"del {variable}",
        "comment": "# Evaluation-only preservation control.",
        "pass": "pass",
        "unrelated_literal": f"{probe} = None",
        "local_annotation": f"{variable}: object",
    }
    kind = variant["mutation"]
    if variant["before_line"] != line:
        raise ValueError("unsupported mutation")
    replacement = lines[line - 1]
    if kind.startswith("alias_"):
        inserted, replacement = alias_change(lines, tree, branch, variable, variant)
    else:
        if kind not in statements:
            raise ValueError("unsupported mutation")
        if kind == "unrelated_literal" and identifier_present(tree, probe):
            raise ValueError("preservation probe collides with original identifier")
        inserted = indent + statements[kind] + "\n"
    if variant["inserted_text"] != inserted:
        raise ValueError("insertion differs from declared mutation")
    inserted_lines = inserted.splitlines(keepends=True)
    changed = lines[: line - 1] + inserted_lines + [replacement] + lines[line:]
    modified = "".join(changed).encode()
    ast.parse(modified)  # Syntax only; never execute corpus code.
    start, end = case["excerpt_lines"]
    excerpt = "".join(changed[start - 1 : end + len(inserted_lines)])
    diff = "".join(
        difflib.unified_diff(
            lines, changed, fromfile="a/" + case["path"], tofile="b/" + case["path"]
        )
    )
    if (
        real.digest(modified) != variant["modified_file_sha256"]
        or excerpt != variant["modified_excerpt"]
        or real.digest(excerpt.encode()) != variant["modified_excerpt_sha256"]
        or diff != variant["unified_diff"]
    ):
        raise ValueError("mutation provenance mismatch")
    return modified


def prepare(manifest, corpus_bytes, repo):
    if manifest["schema"] != "python-decision-flow-counterfactuals/v1":
        raise ValueError("unsupported schema")
    if real.digest(corpus_bytes) != manifest["source_corpus_sha256"]:
        raise ValueError("source corpus digest mismatch")
    corpus = json.loads(corpus_bytes)
    project = manifest["source_project"]
    snapshot = corpus["snapshots"][project]
    if snapshot["revision"] != manifest["source_revision"]:
        raise ValueError("source revision mismatch")
    selected = [p["source_case_id"] for p in manifest["pairs"]]
    cases = {c["id"]: c for c in corpus["cases"] if c["id"] in selected}
    if len(set(selected)) != len(selected) or set(cases) != set(selected):
        raise ValueError("missing or duplicate original case")
    sources = real.load_sources(
        {"snapshots": {project: snapshot}, "cases": list(cases.values())},
        {project: repo},
    )[project]
    license_bytes = subprocess.check_output(
        [
            "git",
            "-C",
            str(repo),
            "show",
            f"{snapshot['revision']}:{snapshot['license_source']}",
        ]
    )
    if (
        real.digest(license_bytes) != snapshot["license_sha256"]
        or license_bytes != (ROOT / snapshot["license_copy"]).read_bytes()
    ):
        raise ValueError("license mismatch")
    runs = []
    ids = set()
    for pair in manifest["pairs"]:
        case = cases[pair["source_case_id"]]
        data = sources[case["path"]]
        if (
            case["project"] != project
            or real.digest(data) != pair["original_file_sha256"]
        ):
            raise ValueError("original source mismatch")
        if case["family"] != pair["family"] or case["source_url"] != pair["source_url"]:
            raise ValueError("original provenance mismatch")
        runs.append(
            (
                case["id"],
                "real_unmodified_control",
                case,
                pair,
                data,
                pair["expected_original"],
                pair["branch_anchor"],
            )
        )
        for variant in pair["variants"]:
            if variant["origin"] != "synthetic_counterfactual":
                raise ValueError("synthetic origin label required")
            modified = materialize_variant(data, case, pair, variant)
            runs.append(
                (
                    variant["id"],
                    variant["origin"],
                    case,
                    pair,
                    modified,
                    variant["expected"],
                    variant["expected_stop"],
                )
            )
    for run in runs:
        if run[0] in ids or real.relative(run[0]).parts != (run[0],):
            raise ValueError("duplicate or unsafe run ID")
        ids.add(run[0])
    real_count = sum(r[1] == "real_unmodified_control" for r in runs)
    if (
        real_count != manifest["original_controls"]
        or len(runs) - real_count != manifest["synthetic_cases"]
        or len({p["family"] for p in manifest["pairs"]}) != manifest["families"]
    ):
        raise ValueError("declared counts mismatch")
    return snapshot, sources, runs


def assess_target(case, report, expected, stop):
    """Join the exact origin and check the declared branch or invalidation stop."""
    observed = real.assess(case, report)
    sites = [
        s
        for s in report["applications"]["sites"]
        if s["path"] == case["analysis_path"]
        and (s["line"], s["column"])
        == (case["call_anchor"]["line"], case["call_anchor"]["column"])
    ]
    rows = [
        r
        for r in report["bindings"]
        if len(sites) == 1 and r["application_id"] == sites[0]["application_id"]
    ]
    row = rows[0] if len(rows) == 1 else {}
    branch = row.get("branch")
    branch_ok = (
        branch is not None and branch["anchor"] == stop
        if expected["flow_status"] == "linked"
        else branch is None
    )
    return observed, row, observed == expected and row.get("stop") == stop and branch_ok


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", required=True, type=Path, help="local SpecGraph Git checkout"
    )
    parser.add_argument(
        "--cases", type=Path, default=Path(__file__).with_name("cases.json")
    )
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--output", type=Path, help="new artifact directory")
    args = parser.parse_args()
    if bool(args.binary) != bool(args.output):
        parser.error("--binary and --output must be supplied together")
    if args.output and args.output.resolve().is_relative_to(args.repo.resolve()):
        parser.error("output must be outside the source repository")
    manifest_bytes = args.cases.read_bytes()
    manifest = json.loads(manifest_bytes)
    snapshot, sources, runs = prepare(
        manifest, (ROOT / "corpus.json").read_bytes(), args.repo
    )
    if not args.binary:
        print(
            json.dumps(
                {
                    "verified_controls": manifest["original_controls"],
                    "verified_synthetic_cases": manifest["synthetic_cases"],
                }
            )
        )
        return 0
    binary = args.binary.resolve()
    binary_hash = real.digest(binary.read_bytes())
    args.output.mkdir(parents=True, exist_ok=False)
    outcomes = []
    for run_id, origin, case, pair, data, expected, stop in runs:
        directory = args.output / run_id
        source_root = directory / "source"
        for path, original in sources.items():
            destination = source_root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data if path == case["path"] else original)
        scope = directory / "scope.toml"
        scope.write_text(
            "schema_version = 1\n[[source_sets]]\nrole = 'application'\npaths = "
            + json.dumps(
                [str(Path(p).relative_to(snapshot["import_root"])) for p in sources]
            )
            + "\n"
        )
        result = subprocess.run(
            [
                str(binary),
                "application-sites",
                str(source_root / snapshot["import_root"]),
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
        report = json.loads(result.stdout)
        applications = report["applications"]
        if applications["provisional"] or report["metric_effect"] != "none":
            raise ValueError(f"incomplete or unexpected metric contract: {run_id}")
        observed, row, agrees = assess_target(case, report, expected, stop)
        outcomes.append(
            {
                "id": run_id,
                "source_case_id": case["id"],
                "family": pair["family"],
                "origin": origin,
                "expected": expected,
                "observed": observed,
                "expected_stop": stop,
                "binding": row,
                "agrees": agrees,
                "source_digest": applications["source_digest"],
                "scope_manifest_digest": applications["scope_manifest_digest"],
                "flow_report_sha256": real.digest(result.stdout),
            }
        )
        metadata = (
            pair
            if origin == "real_unmodified_control"
            else next(v for v in pair["variants"] if v["id"] == run_id)
        )
        if "author_expected_selected_branch_reads_origin" in metadata:
            outcomes[-1]["author_expected_selected_branch_reads_origin"] = metadata[
                "author_expected_selected_branch_reads_origin"
            ]
    assessment = {
        "schema": "python-decision-flow-counterfactual-assessment/v1",
        "cases_sha256": real.digest(manifest_bytes),
        "runner_sha256": real.digest(Path(__file__).read_bytes()),
        "analyzer_binary_sha256": binary_hash,
        "analyzer_contract_source": manifest["analyzer_contract_source"],
        "label_status": manifest["label_status"],
        "metric_effect": "none",
        "original_controls": manifest["original_controls"],
        "synthetic_cases": manifest["synthetic_cases"],
        "families": manifest["families"],
        "agreement": sum(o["agrees"] for o in outcomes),
        "outcomes": outcomes,
    }
    (args.output / "assessment.json").write_text(
        json.dumps(assessment, indent=2) + "\n"
    )
    print(
        json.dumps({k: v for k, v in assessment.items() if k != "outcomes"}, indent=2)
    )
    return 0 if assessment["agreement"] == len(outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
