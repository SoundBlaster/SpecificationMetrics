#!/usr/bin/env python3
"""Freeze independent machine references and score paired family-held-out runs."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random

ROOT = Path(__file__).parent
LABELS = {
    "opportunity": ["eligible", "excluded", "needs_review"],
    "concern_kind": ["policy", "mechanics", "variant_behavior", "unknown"],
}
SEED = "specgraph-jev-family-v1"


def digest(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def prepare(cases):
    packet, mapping = [], {}
    for case in cases:
        encoded = case["vars"]["candidate_json"]
        state = json.loads(encoded)
        opaque = "review-" + hashlib.sha256(encoded.encode()).hexdigest()[:16]
        if opaque in mapping:
            raise ValueError("duplicate blinded context identity")
        mapping[opaque] = state["candidate_id"]
        state["candidate_id"] = opaque
        packet.append({"candidate_id": opaque, "context": state})
    return packet, mapping


def freeze(cases, annotations, mapping):
    """No provisional labels enter the reference or split decision."""
    if annotations.get("reference_kind") != "independent_model_annotation":
        raise ValueError("reference must explicitly identify independent model annotation")
    if not annotations.get("reviewer_id") or any(
        annotations.get(k) is not False for k in ("saw_proposed_labels", "saw_jev_outputs")
    ):
        raise ValueError("reviewer identity and explicit blindness declarations required")
    by_id = {json.loads(c["vars"]["candidate_json"])["candidate_id"]: c for c in cases}
    if (len(by_id) != len(cases) or len(mapping) != len(by_id) or
            len(set(mapping.values())) != len(mapping) or set(mapping.values()) != set(by_id)):
        raise ValueError("mapping must cover corpus exactly")
    expected_mapping = {}
    for case in cases:
        encoded = case["vars"]["candidate_json"]
        state = json.loads(encoded)
        opaque = "review-" + hashlib.sha256(encoded.encode()).hexdigest()[:16]
        expected_mapping[opaque] = state["candidate_id"]
    if mapping != expected_mapping:
        raise ValueError("mapping context identity does not match current candidate JSON")
    seen, reviewed = set(), {}
    for review in annotations["reviews"]:
        opaque = review["candidate_id"]
        if opaque not in mapping or opaque in seen:
            raise ValueError("unknown or duplicate reference ID")
        seen.add(opaque)
        for axis, allowed in LABELS.items():
            if review.get(axis) not in allowed:
                raise ValueError("invalid reference label")
        if not isinstance(review.get("rationale"), str) or not review["rationale"].strip():
            raise ValueError("source rationale required")
        reviewed[mapping[opaque]] = review
    if seen != set(mapping):
        raise ValueError("incomplete reference coverage")
    families = sorted({c["metadata"]["family_id"] for c in cases},
                      key=lambda f: hashlib.sha256((SEED + f).encode()).hexdigest())
    # Select families without labels, before any Jev results. Small holdout is
    # diagnostic, not evidence of a statistically powered deployment threshold.
    holdout = set(families[:max(1, (len(families) + 3) // 4)])
    entries = []
    for original_id, case in by_id.items():
        r = reviewed[original_id]
        state = json.loads(case["vars"]["candidate_json"])
        state["candidate_id"] = r["candidate_id"]
        encoded = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
        family = case["metadata"]["family_id"]
        entries.append({"candidate_id": r["candidate_id"], "source_candidate_id": original_id,
                        "family_id": family, "split": "holdout" if family in holdout else "development",
                        "context": encoded, "context_sha256": digest(encoded.encode()),
                        "opportunity": r["opportunity"], "concern_kind": r["concern_kind"],
                        "rationale": r["rationale"], "missing_context": r.get("missing_context", [])})
    screening = []
    for family in families:
        if family not in holdout and len(screening) < 12:
            screening.append(min(e["candidate_id"] for e in entries if e["family_id"] == family))
    return {"schema_version": 1, "reference_kind": annotations["reference_kind"],
            "reviewer_id": annotations["reviewer_id"], "human_adjudicated": False,
            "seed": SEED, "screening_ids": screening, "cases": entries,
            "selection_rule": "Rank by eligible recall, then precision, then lower abstention; ties by variant ID. Baseline always retained.",
            "targets": {"eligible_recall": 0.90, "eligible_precision": 0.80,
                        "abstention_max": 0.35, "provider_errors": 0},
            "targets_scope": "Provisional discovery targets; machine-reference agreement only, no production or human-gold claim."}


def metrics(pairs, axis):
    labels = LABELS[axis]
    matrix = {truth: {pred: 0 for pred in labels} for truth in labels}
    valid_pairs = []
    errors = 0
    abstain = "needs_review" if axis == "opportunity" else "unknown"
    for truth, prediction in pairs:
        if prediction is None:
            errors += 1
            continue
        matrix[truth][prediction] += 1
        valid_pairs.append((truth, prediction))
    scores = {}
    for label in labels:
        tp = matrix[label][label]
        support = sum(matrix[label].values())
        predicted = sum(row[label] for row in matrix.values())
        recall = tp / support if support else None
        precision = tp / predicted if predicted else None
        f1 = 2 * tp / (support + predicted) if support + predicted else None
        scores[label] = {"support": support, "precision": precision, "recall": recall, "f1": f1}
    count = len(pairs)
    non_abstained = [(t, p) for t, p in valid_pairs if p != abstain]
    valid_f1 = [s["f1"] for s in scores.values() if s["f1"] is not None]
    return {"count": count, "scored_cases": len(valid_pairs), "confusion_matrix": matrix, "per_class": scores,
            "macro_f1": sum(valid_f1) / len(valid_f1) if valid_f1 else None,
            "abstention_rate": sum(p == abstain for _, p in valid_pairs) / count if count else None,
            "scored_abstention_rate": sum(p == abstain for _, p in valid_pairs) / len(valid_pairs) if valid_pairs else None,
            "coverage": len(non_abstained) / count if count else None,
            "non_abstained_error_rate": sum(t != p for t, p in non_abstained) / len(non_abstained) if non_abstained else None,
            "provider_or_contract_errors": errors,
            "false_exclusions": matrix.get("eligible", {}).get("excluded", 0)}


def rows_from_run(run, manifest):
    expected = {e["candidate_id"]: e for e in manifest["cases"]}
    selected = set(run["candidate_ids"])
    if not selected or not selected <= set(expected):
        raise ValueError("unknown or empty evaluated set")
    providers = run["variant_ids"]
    if not providers or len(set(providers)) != len(providers) or len(selected) != len(run["candidate_ids"]):
        raise ValueError("duplicate or empty evaluated IDs")
    if any(expected[c]["split"] != run["phase"] for c in selected):
        raise ValueError("run crosses development/holdout boundary")
    rows = {}
    for row in run["results"]["results"]:
        if "vars" in row:
            candidate_id = json.loads(row["vars"]["candidate_json"])["candidate_id"]
            context_digest = digest(row["vars"]["candidate_json"].encode())
        else:
            candidate_id = row["candidate_id"]
            context_digest = row["context_sha256"]
        variant = row["provider"]["id"]
        key = (variant, candidate_id)
        if variant not in providers or candidate_id not in selected or key in rows:
            raise ValueError("duplicate or unexpected evaluation row")
        if context_digest != expected[candidate_id]["context_sha256"]:
            raise ValueError("evaluated context differs from frozen input")
        response = row.get("response", {})
        output = response.get("output", {})
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except ValueError:
                output = {}
        if not isinstance(output, dict):
            output = {}
        predictions = {}
        for axis, allowed in LABELS.items():
            answer = output.get(axis, {})
            choice = answer.get("choice") if isinstance(answer, dict) else None
            predictions[axis] = choice if choice in allowed and not response.get("error") and not row.get("error") else None
        rows[key] = predictions
    if set(rows) != {(v, c) for v in providers for c in selected}:
        raise ValueError("missing evaluation rows; incomplete runs cannot be scored")
    return expected, rows


def summarize(run, manifest):
    expected, rows = rows_from_run(run, manifest)
    summaries = {}
    for variant in run["variant_ids"]:
        summaries[variant] = {axis: metrics([(expected[c][axis], rows[variant, c][axis])
                                           for c in run["candidate_ids"]], axis) for axis in LABELS}
    return {"reference_kind": manifest["reference_kind"], "human_adjudicated": False,
            "phase": run["phase"], "variants": summaries,
            "limits": "Agreement with one blind model reviewer on a purposive challenge corpus; not measured human accuracy or production prevalence."}


def paired_interval(run, manifest, baseline, challenger, draws=2000):
    expected, rows = rows_from_run(run, manifest)
    groups = {}
    for c in run["candidate_ids"]:
        groups.setdefault(expected[c]["family_id"], []).append(c)
    families = sorted(groups)
    rng = random.Random(SEED)
    deltas = []
    for _ in range(draws):
        ids = [c for _ in families for c in groups[rng.choice(families)]]
        eligible = [c for c in ids if expected[c]["opportunity"] == "eligible"]
        if eligible:
            deltas.append(sum((rows[challenger, c]["opportunity"] == "eligible") -
                              (rows[baseline, c]["opportunity"] == "eligible") for c in eligible) / len(eligible))
    if not deltas:
        return {"eligible_recall_delta_interval": None, "reason": "No eligible reference cases"}
    deltas.sort()
    return {"eligible_recall_delta_interval": [deltas[int(.025 * (len(deltas) - 1))],
                                              deltas[int(.975 * (len(deltas) - 1))]],
            "resampling_unit": "whole decision family", "draws_with_eligible": len(deltas),
            "limits": "Small-family diagnostic percentile bootstrap; no statistical-power claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--output", type=Path, required=True)
    f = sub.add_parser("freeze")
    f.add_argument("--annotations", type=Path, required=True)
    f.add_argument("--mapping", type=Path, required=True)
    f.add_argument("--output", type=Path, required=True)
    s = sub.add_parser("score")
    s.add_argument("--manifest", type=Path, required=True)
    s.add_argument("--run", type=Path, required=True)
    s.add_argument("--output", type=Path, required=True)
    s.add_argument("--select", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        from validate_cases import validate
        cases = json.loads((ROOT / "corpus/cases.json").read_text())
        validate(cases)
        packet, mapping = prepare(cases)
        args.output.mkdir()
        write(args.output / "packet.json", packet)
        write(args.output / "mapping.json", mapping)
        print(f"Prepared {len(packet)} blinded contexts; no labels in reviewer packet")
    elif args.command == "freeze":
        value = freeze(json.loads((ROOT / "corpus/cases.json").read_text()),
                       json.loads(args.annotations.read_text()), json.loads(args.mapping.read_text()))
        if args.output.exists():
            raise ValueError("refusing to overwrite frozen manifest")
        write(args.output, value)
        print(f"Frozen {len(value['cases'])} model-reference cases; no hosted requests")
    else:
        manifest = json.loads(args.manifest.read_text())
        run = json.loads(args.run.read_text())
        if run["manifest_sha256"] != digest(args.manifest.read_bytes()):
            raise ValueError("run manifest digest mismatch")
        report = summarize(run, manifest)
        if "baseline-v1" in run["variant_ids"]:
            report["paired_comparisons"] = {v: paired_interval(run, manifest, "baseline-v1", v)
                                            for v in run["variant_ids"] if v != "baseline-v1"}
        if args.select:
            if run["phase"] != "development":
                raise ValueError("cannot select prompts on holdout")
            if args.select.exists():
                raise ValueError("refusing to overwrite frozen finalists")
            if any(report["variants"][v][axis]["provider_or_contract_errors"]
                   for v in run["variant_ids"] for axis in LABELS):
                raise ValueError("provider/contract errors require diagnosis before prompt selection")
            challengers = [v for v in run["variant_ids"] if v != "baseline-v1"]
            def rank(v):
                m = report["variants"][v]["opportunity"]
                e = m["per_class"]["eligible"]
                return (-(e["recall"] or 0), -(e["precision"] or 0), m["abstention_rate"], v)
            best = min(challengers, key=rank)
            write(args.select, {"variant_ids": ["baseline-v1", best],
                                "manifest_sha256": run["manifest_sha256"],
                                "prompt_configs": {v: run["prompt_configs"][v] for v in ("baseline-v1", best)},
                                "development_run_sha256": digest(args.run.read_bytes())})
        write(args.output, report)
        print(json.dumps(report["variants"], ensure_ascii=False))


if __name__ == "__main__":
    main()
