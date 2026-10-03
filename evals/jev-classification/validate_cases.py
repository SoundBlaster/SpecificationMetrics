#!/usr/bin/env python3
"""Validate the checked-in Jev pilot cases without making provider calls."""

import json
from pathlib import Path

ROOT = Path(__file__).parent
EXPECTED = {
    "expected_opportunity": {"eligible", "excluded", "needs_review"},
    "expected_concern_kind": {"policy", "mechanics", "variant_behavior", "unknown"},
}


def main() -> int:
    cases = json.loads((ROOT / "cases.json").read_text())
    if not isinstance(cases, list) or not cases:
        raise SystemExit("cases.json must contain at least one case")

    seen = set()
    for index, case in enumerate(cases, start=1):
        description = case.get("description", f"case {index}")
        variables = case.get("vars")
        if not isinstance(variables, dict):
            raise SystemExit(f"{description}: vars must be a mapping")
        try:
            candidate = json.loads(variables["candidate_json"])
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise SystemExit(f"{description}: candidate_json must be valid JSON: {error}")

        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise SystemExit(f"{description}: candidate_id is required")
        if candidate_id in seen:
            raise SystemExit(f"duplicate candidate_id: {candidate_id}")
        seen.add(candidate_id)

        for key, allowed in EXPECTED.items():
            if variables.get(key) not in allowed:
                raise SystemExit(f"{description}: {key} must be one of {sorted(allowed)}")
        if variables.get("label_status") != "pilot_hypothesis":
            raise SystemExit(f"{description}: labels must remain marked pilot_hypothesis")

    print(f"validated {len(cases)} Jev pilot case(s); no API requests made")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
