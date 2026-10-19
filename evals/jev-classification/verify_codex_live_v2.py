"""Stricter offline consumer; the v1 capture and replay remain frozen."""

import json

import verify_codex_live_v1 as historical
from verify_codex_one_packet_v1 import load, require


def validate(value, schema):
    """Validate the object/string/enum subset used by the frozen schema."""
    kind = schema["type"]
    if kind == "object":
        require(isinstance(value, dict), "schema object required")
        properties = schema["properties"]
        require(set(schema["required"]) <= set(value), "schema required properties")
        require(schema["additionalProperties"] is False and set(value) <= set(properties),
                "schema additional properties")
        for key, item in value.items():
            validate(item, properties[key])
    elif kind == "string":
        require(isinstance(value, str) and value in schema["enum"], "schema enum label")
    else:
        raise ValueError(f"unsupported frozen schema type: {kind}")


def verify(bundle=historical.BUNDLE):
    prepared = load(bundle / "prepared.json")
    validate(load(bundle / "answer.json"), prepared["response_schema"])
    comparison = load(bundle / "comparison.json")
    axes = comparison["axes"]
    matching = sum(row["codex_label"] == row["sol_label"] for row in axes)
    summary = dict(matching_axes=matching, total_axes=len(axes),
                   complete_view_agreement=matching == len(axes))
    require(comparison["agreement_with_sol"] == summary, "derived agreement summary")
    result = historical.verify(bundle)
    require(result["matching_axes"] == matching
            and result["complete_view_agreement"] == summary["complete_view_agreement"],
            "historical summary disagrees with axes")
    return dict(result, consumer="specmetrics.codex-live-replay/v2")


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
