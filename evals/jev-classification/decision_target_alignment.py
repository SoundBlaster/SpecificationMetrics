#!/usr/bin/env python3
"""Bind explicit development-case selectors to the Rust decision-target export.

Offline only. Changed targets require fresh annotation: old labels and provider
answers are deliberately not copied into this artifact.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from ownership_gate import construction_evidence
from question_grouping import digest
from scanner_build import verified_build, verify_unchanged

ROOT = Path(__file__).parent


def anchor_position(site, needle):
    code = site["code"]
    if code.count(needle) != 1:
        raise ValueError("Selection needle must occur exactly once inside the source container")
    before = code[:code.index(needle)]
    return site["start_line"] + before.count("\n"), len(before.rsplit("\n", 1)[-1].encode()) + 1


def build(repo, scanner, selectors):
    if selectors["schema_version"] != 1 or selectors["study_kind"] != "explicit_target_alignment":
        raise ValueError("Invalid selector contract")
    corpus = {c["description"]: c["metadata"]["source"]["site"] for c in json.loads((ROOT/"corpus/cases.json").read_text())}
    entries = selectors["cases"]
    ids = [e["source_candidate_id"] for e in entries]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Empty or duplicate selected cases")
    scanner_provenance = verified_build(ROOT.parent.parent, scanner)
    results = []
    with tempfile.TemporaryDirectory(prefix="specmetrics-target-") as temporary:
        for entry in entries:
            cid = entry["source_candidate_id"]
            site = corpus[cid]
            raw = subprocess.check_output(["git", "-C", str(repo), "show", site["revision"] + ":" + site["path"]])
            # Verify full file, exact container, source span and construction facts.
            ownership = construction_evidence(raw, site)
            line, column = anchor_position(site, entry["anchor_text"])
            root = Path(temporary)/cid
            path = root/site["path"]
            path.parent.mkdir(parents=True)
            path.write_bytes(raw)
            args = [str(scanner), "extract-decision-target", str(root), "--path", site["path"],
                    "--line", str(line), "--column", str(column), "--syntax-kind", entry["syntax_kind"], "--select", entry["select"]]
            extracted = subprocess.run(args, check=True, capture_output=True)
            target = json.loads(extracted.stdout)
            span = target["expression"]["span"]
            selected = raw[span["start_byte"]:span["end_byte"]].decode()
            container_start = len("".join(raw.decode().splitlines(keepends=True)[:site["start_line"] - 1]).encode())
            container_end = container_start + len(site["code"].encode())
            if (selected != target["expression"]["code"] or target["expression"]["truncated"]
                    or not container_start <= span["start_byte"] < span["end_byte"] <= container_end):
                raise ValueError("Target bytes are not bound to the reviewed source container")
            scan = json.loads(subprocess.run([str(scanner), "scan", str(root)], check=True, capture_output=True).stdout)
            if scan["parse_issues"]:
                raise ValueError("Historical scan has parse issues")
            links = [c["fingerprint"] for c in scan["candidates"] if c["path"] == site["path"] and c["line"] == line and c["column"] == column]
            results.append({"source_candidate_id": cid, "source": ownership["source"],
                            "selector": entry, "target": target,
                            "legacy_anchor_fingerprints": links,
                            "legacy_mapping_status": "exact_anchor_match" if links else "no_anchor_match",
                            "construction_evidence": ownership,
                            "reference_status": "requires_new_annotation",
                            "prior_labels_transferred": False})
    verify_unchanged(ROOT.parent.parent, scanner, scanner_provenance)
    return {"schema_version": 1, "study_kind": "explicit_target_alignment", "new_inference_requests": 0,
            "planned_cases": len(entries), "extracted_targets": len(results), "cases": results,
            "selector_manifest_sha256": digest(json.dumps(selectors, sort_keys=True, separators=(",", ":")).encode()),
            "corpus_sha256": digest((ROOT/"corpus/cases.json").read_bytes()),
            "implementation_digests": {name: digest((ROOT/name).read_bytes()) for name in ["decision_target_alignment.py", "ownership_gate.py", "scanner_build.py", "experiment.py", "question_grouping.py"]},
            "scanner_provenance": scanner_provenance,
            "limits": "Explicit agent-proposed development selectors, not automatic discovery or human-approved targets. Exact anchor mapping is syntactic, not a registry fingerprint migration. New expression units need new semantic annotations. Construction facts refer to their verified containing assignment; the Rust target itself reports ownership unknown. No production classification, registry, S/U, network or provider calls."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path, required=True)
    parser.add_argument("--scanner", type=Path, required=True)
    parser.add_argument("--selectors", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build(args.source_repo, args.scanner.resolve(), json.loads(args.selectors.read_text()))
    with args.output.open("x") as out:
        json.dump(report, out, indent=2)
        out.write("\n")
    print(json.dumps({"planned": report["planned_cases"], "extracted": report["extracted_targets"],
                      "legacy_anchor_matches": sum(bool(c["legacy_anchor_fingerprints"]) for c in report["cases"]), "new_inference_requests": 0}))


if __name__ == "__main__":
    main()
