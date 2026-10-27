#!/usr/bin/env python3
"""Check frozen alias expectations with the reference, optionally using local Git."""

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from model import CONTRACT, analyze, literal


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "evals/python-decision-flow-v1"
MATRIX_SHA256 = "00b1f9212c9f86dbb768ca98dc7bee9f86617ab9a6c5d2f631b1ff125803c333"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_matrix(path):
    raw = path.read_bytes()
    if digest(raw) != MATRIX_SHA256:
        raise ValueError("frozen 47-case contract matrix changed")
    matrix = json.loads(raw)
    if matrix["schema"] != CONTRACT or matrix["status"] != "proposed_not_implemented":
        raise ValueError("unsupported frozen contract matrix")
    return raw, matrix


def enum_preconditions(code, case_id):
    """Audited frozen-fixture facts, not a general Python enum resolver."""
    import ast

    names = {
        "specgraph-02": ("_AcceptanceCriterionDisposition", "ADD_PLACEHOLDER"),
        "specgraph-03": ("_UnsupportedClaimDisposition", "DOWNGRADE"),
    }
    if case_id not in names:
        return set(), None
    class_name, member_name = names[case_id]
    tree = ast.parse(code)
    imports = [
        n
        for n in tree.body
        if isinstance(n, ast.ImportFrom)
        and n.module == "enum"
        and n.level == 0
        and any(a.name == "Enum" and a.asname is None for a in n.names)
    ]
    classes = [
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name
    ]
    if len(imports) != 1 or len(classes) != 1:
        raise ValueError("frozen enum import/class fact unavailable")
    cls = classes[0]
    if (
        cls.decorator_list
        or len(cls.bases) != 1
        or not isinstance(cls.bases[0], ast.Name)
        or cls.bases[0].id != "Enum"
    ):
        raise ValueError("frozen enum base changed")
    members = []
    for node in cls.body:
        if (
            not isinstance(node, ast.Assign)
            or len(node.targets) != 1
            or not isinstance(node.targets[0], ast.Name)
            or not literal(node.value)
        ):
            raise ValueError("frozen enum member shape changed")
        members.append(node.targets[0].id)
    if len(members) != len(set(members)) or member_name not in members:
        raise ValueError("frozen enum member missing/ambiguous")
    if any(
        isinstance(n, ast.Name)
        and isinstance(n.ctx, ast.Store)
        and n.id in (class_name, "Enum")
        or isinstance(n, ast.arg)
        and n.arg in (class_name, "Enum")
        for n in ast.walk(tree)
    ):
        raise ValueError("frozen enum name rebound/shadowed")
    excerpt = ast.get_source_segment(code, cls)
    return {(class_name, member_name)}, {
        "class": class_name,
        "member": member_name,
        "class_source_sha256": digest(excerpt.encode()),
        "basis": "exact frozen source, simple enum import/base/members; prior v1 enum proof assumed",
    }


def unit_results(matrix):
    outcomes = []
    ids = set()
    for case in matrix["unit_cases"]:
        if case["id"] in ids:
            raise ValueError("duplicate unit ID")
        ids.add(case["id"])
        result = analyze(
            case["code"],
            case["target_origin"],
            case["origin_projection"],
            origin_id=case["id"],
            origin_proven=True,
            limits=matrix["defaults"],
        )
        outcomes.append(
            {
                "id": case["id"],
                "origin": case["origin"],
                "expected": case["expected"],
                **result,
                "agrees": result["outcome"] == case["expected"],
            }
        )
    return outcomes


def source_results(matrix, repo):
    spec = importlib.util.spec_from_file_location(
        "counterfactual_replay", CORPUS / "counterfactuals/invalidation-v1/replay.py"
    )
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    manifest_path = ROOT / matrix["frozen_alias_manifest"]["path"]
    manifest_bytes = manifest_path.read_bytes()
    if digest(manifest_bytes) != matrix["frozen_alias_manifest"]["sha256"]:
        raise ValueError("frozen alias manifest mismatch")
    manifest = json.loads(manifest_bytes)
    snapshot, sources, runs = replay.prepare(
        manifest, (CORPUS / "corpus.json").read_bytes(), repo
    )
    original = json.loads((CORPUS / "corpus.json").read_bytes())
    cases = {c["id"]: c for c in original["cases"]}
    prior_bytes = (CORPUS / "counterfactuals/alias-v1/assessment.json").read_bytes()
    prior = {o["id"]: o for o in json.loads(prior_bytes)["outcomes"]}
    declared = {c["id"]: c for c in matrix["source_backed_expectations"]}
    expected_ids = {r[0] for r in runs if r[1] == "synthetic_counterfactual"}
    if (
        len(declared) != len(matrix["source_backed_expectations"])
        or set(declared) != expected_ids
    ):
        raise ValueError("missing/duplicate source expectations")
    outcomes = []
    for run_id, origin, case, pair, data, _, _ in runs:
        evidence = prior[run_id]
        if evidence["observed"]["call_category"] != "direct_application":
            raise ValueError("prior recognized-origin precondition unavailable")
        code = data.decode()
        projection = evidence["binding"]["origin_projection"] or "raw"
        facts, enum_receipt = enum_preconditions(code, case["id"])
        result = analyze(
            code,
            cases[case["id"]]["call_anchor"],
            projection,
            origin_id=evidence["binding"]["application_id"],
            origin_proven=True,
            enum_facts=facts,
            limits=matrix["defaults"],
        )
        if origin == "synthetic_counterfactual":
            target = declared[run_id]
            if digest(data) != target["modified_file_sha256"]:
                raise ValueError("mutated source mismatch")
            expected = dict(target["proposed_alias_profile_expected"])
            name = expected.pop("reference_name")
            state = {
                "local_alias_read": "origin",
                "branch_reference_rebound": "other",
                "branch_reference_deleted": "deleted",
            }[expected["reason"]]
            expected["reference"] = {"name": name, "state": state}
        else:
            expected = {
                "status": "linked",
                "reason": "local_alias_read",
                "stop": pair["branch_anchor"],
                "reference": {"name": pair["variable"], "state": "origin"},
            }
        outcomes.append(
            {
                "id": run_id,
                "source_case_id": case["id"],
                "origin": origin,
                "source_revision": snapshot["revision"],
                "source_path": case["path"],
                "source_file_sha256": digest(data),
                "origin_precondition": "resolved direct_application in frozen v1 assessment",
                "enum_precondition": enum_receipt,
                "expected": expected,
                **result,
                "agrees": result["outcome"] == expected,
            }
        )
    return outcomes, {
        "prior_v1_assessment_sha256": digest(prior_bytes),
        "snapshot_files": len(sources),
        "factory_and_enum_resolution": "supplied preconditions; not independently proved by transfer model",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        help="optional local SpecGraph clone containing frozen revision",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="new external run directory; omit to print summary only",
    )
    args = parser.parse_args()
    if args.output and any(
        args.output.resolve().is_relative_to(p.resolve())
        for p in (ROOT, *([args.repo] if args.repo else []))
    ):
        parser.error("output must be outside the source checkouts")
    raw, matrix = load_matrix(ROOT / "docs/local-alias-flow-cases.json")
    units = unit_results(matrix)
    sources, preconditions = (
        source_results(matrix, args.repo) if args.repo else ([], None)
    )
    report = {
        "schema": "specification-metrics.local-alias-reference-assessment/v1",
        "matrix_sha256": digest(raw),
        "model_sha256": digest(Path(__file__).with_name("model.py").read_bytes()),
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "python_version": sys.version.split()[0],
        "unit_cases": len(units),
        "unit_agreement": sum(o["agrees"] for o in units),
        "source_alias_cases": sum(
            o["origin"] == "synthetic_counterfactual" for o in sources
        ),
        "source_controls": sum(
            o["origin"] == "real_unmodified_control" for o in sources
        ),
        "source_agreement": sum(o["agrees"] for o in sources),
        "source_status_counts": dict(Counter(o["outcome"]["status"] for o in sources)),
        "source_phase": "checked" if args.repo else "not_requested",
        "provided_preconditions": preconditions,
        "production_profile_implemented": False,
        "metric_effect": "none",
        "unit_outcomes": units,
        "source_outcomes": sources,
    }
    if args.output:
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / "assessment.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in ("unit_outcomes", "source_outcomes")
            },
            indent=2,
        )
    )
    return 0 if all(o["agrees"] for o in [*units, *sources]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
