#!/usr/bin/env python3
"""Offline matched-rubric scoring with explicit incomplete-run denominators."""
import argparse
import json
from pathlib import Path
from experiment import LABELS, metrics
from question_grouping import canonical, digest, parse_response
from rubric_alignment import load
from state_key_order import load_wire

ROOT = Path(__file__).parent


def score(run):
    manifest, plan = load(run)
    rows = [json.loads(line) for line in (run/"responses.jsonl").read_text().splitlines()]
    receipt = json.loads((run/"receipt.json").read_text())
    if (len(rows)>len(plan) or receipt["attempted_requests"]!=len(rows)
            or receipt["planned_requests"]!=32 or type(receipt["completed"]) is not bool):
        raise ValueError("Invalid receipt")
    if receipt["completed"] and (len(rows)!=32 or any(r["error"] for r in rows) or receipt["stop_reason"] is not None):
        raise ValueError("False completion")
    indexed = {}
    for item,row in zip(plan,rows):
        if any(item[k]!=row[k] for k in ["candidate_id","arm","repeat","wire_sha256"]):
            raise ValueError("Response does not match ordered plan")
        if row["error"] is None:
            parse_response(canonical(row["response"]),load_wire(item)[1]["questions"])
        indexed[item["candidate_id"],item["arm"],item["repeat"]]=row
    annotation = json.loads((run/"annotations.json").read_text())
    if annotation["packet_sha256"]!=digest((run/"reference-packet.json").read_bytes()):
        raise ValueError("Reference packet provenance mismatch")
    mapping = json.loads((run/"reference-mapping.json").read_text())
    refs = {a["case_id"]:a for a in annotation["annotations"]}
    if len(annotation["annotations"])!=8 or set(refs)!={m["case_id"] for m in mapping}:
        raise ValueError("Invalid reference coverage")
    for a in refs.values():
        if any(a[axis] not in LABELS[axis] for axis in LABELS):
            raise ValueError("Unknown reference label")
    refs = {m["candidate_id"]:refs[m["case_id"]] for m in mapping}
    old_mapping=json.loads((ROOT/"runs/2026-10-05-intent-profile-reference/mapping.json").read_text())["entries"]
    source_ids={m["ablation_candidate_id"]:m["source_candidate_id"] for m in old_mapping}
    cases=[]
    for cid,ref in refs.items():
        predictions={}
        for repeat in [1,2]:
            predictions[str(repeat)]={}
            for arm in ["baseline","aligned"]:
                row=indexed.get((cid,arm,repeat))
                predictions[str(repeat)][arm]={axis:row["response"]["answers"][axis]["choice"] if row and row["error"] is None else None for axis in LABELS}
        cases.append({"candidate_id":cid,"source_candidate_id":source_ids[cid],"reference":{axis:ref[axis] for axis in LABELS},"predictions":predictions})
    summaries={}
    for repeat in ["1","2"]:
        summaries[repeat]={}
        for arm in ["baseline","aligned"]:
            summaries[repeat][arm]={}
            for axis in LABELS:
                pairs=[(c["reference"][axis],c["predictions"][repeat][arm][axis]) for c in cases]
                m=metrics(pairs,axis)
                m["unscored_cases"]=m.pop("provider_or_contract_errors")
                m["not_run_cases"]=sum((c["candidate_id"],arm,int(repeat)) not in indexed for c in cases)
                m["agreement_count"]=sum(a==b for a,b in pairs)
                m["agreement_denominator"]=8
                summaries[repeat][arm][axis]=m
    controls={}
    for repeat in ["1","2"]:
        controls[repeat]={}
        for arm in ["baseline","aligned"]:
            controls[repeat][arm]={
                "owned_false_positive_ids":[c["source_candidate_id"] for c in cases if c["source_candidate_id"] in {"sg-018","sg-020"} and c["predictions"][repeat][arm]["opportunity"]=="eligible"],
                "mechanics_false_positive_ids":[c["source_candidate_id"] for c in cases if c["source_candidate_id"] in {"sg-031","sg-032","sg-034"} and c["predictions"][repeat][arm]["opportunity"]=="eligible"],
            }
    supported=None
    if receipt["completed"]:
        supported=all(summaries[r]["aligned"]["opportunity"]["agreement_count"]>summaries[r]["baseline"]["opportunity"]["agreement_count"]
            and summaries[r]["aligned"]["opportunity"]["per_class"]["eligible"]["recall"]>summaries[r]["baseline"]["opportunity"]["per_class"]["eligible"]["recall"]
            and all(not(set(controls[r]["aligned"][kind])-set(controls[r]["baseline"][kind])) for kind in controls[r]["aligned"])
            for r in ["1","2"])
    usage={arm:{k:sum(((r.get("response") or {}).get("usage") or {}).get(k,0) for r in rows if r["arm"]==arm and r["error"] is None) for k in ["input_tokens","output_tokens"]} for arm in ["baseline","aligned"]}
    implementation={name:digest((ROOT/name).read_bytes()) for name in ["score_rubric_alignment.py","rubric_alignment.py","question_grouping.py","state_key_order.py","experiment.py"]}
    artifacts={name:digest((run/name).read_bytes()) for name in ["manifest.json","annotations.json","reference-mapping.json","responses.jsonl","receipt.json"]}
    artifacts["historical_source_mapping"]=digest((ROOT/"runs/2026-10-05-intent-profile-reference/mapping.json").read_bytes())
    return {"schema_version":1,"study_kind":manifest["study_kind"],"completed":receipt["completed"],"reference_kind":"independent_model_annotation","human_adjudicated":False,"holdout":False,"receipt":receipt,"summaries":summaries,"controls":controls,"cases":cases,"usage":usage,"alignment_hypothesis_supported":supported,"analysis_implementation_digests":implementation,"artifact_digests":artifacts,"limits":"Eight diagnostic development cases, two repeats and one model reference. Composite wording intervention; not proof of individual word causality, calibrated confidence, human accuracy or generalization."}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    report=score(args.run)
    with args.output.open("x") as out:
        json.dump(report,out,indent=2)
        out.write("\n")
    print(json.dumps({"completed":report["completed"],"alignment_hypothesis_supported":report["alignment_hypothesis_supported"],"agreement":{r:{arm:{axis:m["agreement_count"] for axis,m in axes.items()} for arm,axes in arms.items()} for r,arms in report["summaries"].items()},"controls":report["controls"],"usage":report["usage"]}))


if __name__ == "__main__":main()
