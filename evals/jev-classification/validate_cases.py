#!/usr/bin/env python3
"""Validate the checked-in Jev pilot cases without making provider calls."""

import json
import hashlib
from pathlib import Path
import re

ROOT = Path(__file__).parent
EXPECTED = {
    "expected_opportunity": {"eligible", "excluded", "needs_review"},
    "expected_concern_kind": {"policy", "mechanics", "variant_behavior", "unknown"},
}


FORBIDDEN_CONTEXT_KEYS = {
    "prior_diagnostic", "expected_opportunity", "expected_concern_kind",
    "label_status", "label_rationale", "proposed_opportunity", "proposed_concern_kind",
    "classification_status", "review_status", "family_id", "history", "role",
}


def _assert_no_label_leak(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_CONTEXT_KEYS:
                raise ValueError(f"model context contains evaluation-only key: {key}")
            _assert_no_label_leak(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_label_leak(item)


def _digest(value):
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate(cases):
    if not isinstance(cases, list) or not cases:
        raise ValueError("dataset must contain at least one case")

    seen = set()
    family_splits = {}
    for index, case in enumerate(cases, start=1):
        description = case.get("description", f"case {index}")
        variables = case.get("vars")
        if not isinstance(variables, dict):
            raise ValueError(f"{description}: vars must be a mapping")
        try:
            candidate = json.loads(variables["candidate_json"])
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError(f"{description}: candidate_json must be valid JSON: {error}") from error

        if not isinstance(candidate, dict):
            raise ValueError(f"{description}: candidate_json must be an object")
        _assert_no_label_leak(candidate)
        if len(variables["candidate_json"].encode("utf-8")) > 24 * 1024:
            raise ValueError(f"{description}: model context exceeds 24 KiB")

        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise ValueError(f"{description}: candidate_id is required")
        if candidate_id in seen:
            raise ValueError(f"duplicate candidate_id: {candidate_id}")
        seen.add(candidate_id)

        for key, allowed in EXPECTED.items():
            if variables.get(key) not in allowed:
                raise ValueError(f"{description}: {key} must be one of {sorted(allowed)}")
        if variables.get("label_status") != "pilot_hypothesis":
            raise ValueError(f"{description}: labels must remain marked pilot_hypothesis")

        metadata = case.get("metadata", {})
        if "source" not in metadata:
            raise ValueError(f"{description}: immutable source provenance is required")
        if metadata.get("review_status") != "unreviewed":
            raise ValueError(f"{description}: these agent proposals must remain unreviewed")
        if metadata.get("context_sha256") != _digest(variables["candidate_json"]):
            raise ValueError(f"{description}: context digest mismatch")
        family, split = metadata.get("family_id"), metadata.get("split")
        if not family or split not in {"unassigned", "development", "holdout"}:
            raise ValueError(f"{description}: family and split are required")
        if family in family_splits and family_splits[family] != split:
            raise ValueError(f"{description}: related family appears in different splits")
        family_splits[family] = split
        source = metadata["source"]
        site = source["site"]
        if candidate.get("site", {}).get("code") != site["code"]:
            raise ValueError(f"{description}: source site and model excerpt differ")
        if (candidate["source"]["path"], candidate["source"]["symbol"]) != (site["path"], site["symbol"]):
            raise ValueError(f"{description}: source locator mismatch")
        for record in [site] + source.get("supporting", []):
            if not re.fullmatch(r"[0-9a-f]{40}", record["revision"]):
                raise ValueError(f"{description}: a full source commit is required")
            if record["excerpt_sha256"] != _digest(record["code"]):
                raise ValueError(f"{description}: source excerpt digest mismatch")
            if record["start_line"] < 1 or record["end_line"] < record["start_line"]:
                raise ValueError(f"{description}: invalid source span")
        model_support = candidate["bounded_context"]["supporting_code"]
        expected_support = [{"path": r["path"], "symbol": r["symbol"], "code": r["code"]}
                            for r in source.get("supporting", [])]
        if model_support != expected_support:
            raise ValueError(f"{description}: supporting source and model context differ")
    return len(cases)


def main() -> int:
    count = 0
    for path in [ROOT / "cases.json", ROOT / "corpus" / "cases.json"]:
        count += validate(json.loads(path.read_text()))

    print(f"validated {count} cases across smoke/corpus datasets; no API requests made")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
