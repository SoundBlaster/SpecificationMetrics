"""Validate a model reference against the exact task and supplied evidence only."""
from question_grouping import canonical, digest


def validate(packet, reference):
    if reference["authority"] != "independent_model_reference_not_human_gold":
        raise ValueError("Unexpected reference authority")
    if reference["packet_sha256"] != digest(canonical(packet)):
        raise ValueError("Reference task digest mismatch")
    cases = {c["case_id"]: c for c in packet["cases"]}
    rows = reference["annotations"]
    if len(rows) != len(cases) or {r["case_id"] for r in rows} != set(cases):
        raise ValueError("Expected exactly one annotation for every task case")
    for row in rows:
        case = cases[row["case_id"]]
        if (row["status"] != "annotated" or row["state_sha256"] != case["state_sha256"]
                or row["state_sha256"] != digest(canonical(case["state"]))):
            raise ValueError("Incomplete annotation or changed task state")
        for axis in ["opportunity", "concern_kind"]:
            if row[axis] not in packet["questions"][axis]["criteria"]:
                raise ValueError("Annotation uses an unknown rubric label")
        evidence = row["evidence"]
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("Every annotation needs source evidence")
        sources = {"target": case["state"]["target"]["code"],
                   **{f["fragment_id"]: f["code"] for f in case["state"]["bounded_context"]["fragments"]}}
        for item in evidence:
            quote, reason = item["quote"], item["reason"]
            if (item["location"] not in sources or not isinstance(quote, str) or not quote.strip()
                    or quote not in sources[item["location"]] or not isinstance(reason, str) or not reason.strip()):
                raise ValueError("Evidence must quote the supplied target or fragment exactly")
        if (not isinstance(row["uncertainties"], list)
                or any(not isinstance(u, str) or not u.strip() for u in row["uncertainties"])):
            raise ValueError("Expected explicit uncertainty strings")
    return {"annotated_cases": len(rows), "packet_sha256": reference["packet_sha256"],
            "authority": reference["authority"], "evidence_validation": "passed"}
