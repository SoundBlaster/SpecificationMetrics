import argparse
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--repo", type=pathlib.Path, required=True)
parser.add_argument("--binary", type=pathlib.Path, required=True)
parser.add_argument("--temp-root", type=pathlib.Path, required=True)
args = parser.parse_args()
root = pathlib.Path(__file__).resolve().parents[2]
temp_root = args.temp_root.resolve()
if temp_root.is_relative_to(root) or temp_root.is_relative_to(args.repo.resolve()):
    parser.error("temporary files must be outside both source repositories")
p = root / "evals/python-decision-flow-v1/counterfactuals/invalidation-v1/replay.py"
spec = importlib.util.spec_from_file_location("replay", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
manifest = json.loads(
    (
        root / "evals/python-decision-flow-v1/counterfactuals/alias-v1/cases.json"
    ).read_bytes()
)
snapshot, sources, runs = mod.prepare(
    manifest,
    (root / "evals/python-decision-flow-v1/corpus.json").read_bytes(),
    args.repo,
)
ref = {
    x["id"]: x["outcome"]
    for x in json.loads(
        (root / "evals/local-alias-reference-v1/assessment.json").read_bytes()
    )["source_outcomes"]
}
binary_path = args.binary.resolve()
binary = str(binary_path)
results = []
if len(runs) != 15 or len(ref) != 15 or {run[0] for run in runs} != set(ref):
    raise ValueError("expected exactly the 15 frozen source cases")
with tempfile.TemporaryDirectory(dir=temp_root) as temp:
    for run_id, origin, case, pair, data, expected, stop in runs:
        base = pathlib.Path(temp) / run_id
        src = base / "source"
        for path, original in sources.items():
            dest = src / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data if path == case["path"] else original)
        scope = base / "scope.toml"
        scope.write_text(
            "schema_version = 1\n[[source_sets]]\nrole = 'application'\npaths = "
            + json.dumps(
                [
                    str(pathlib.Path(p).relative_to(snapshot["import_root"]))
                    for p in sources
                ]
            )
            + "\n"
        )
        report = json.loads(
            subprocess.check_output(
                [
                    binary,
                    "application-sites",
                    str(src / snapshot["import_root"]),
                    "--profile",
                    "python-decision-flow-alias-v1",
                    "--scope-manifest",
                    str(scope),
                ]
            )
        )
        site = next(
            s
            for s in report["applications"]["sites"]
            if s["path"] == case["analysis_path"]
            and (s["line"], s["column"])
            == (case["call_anchor"]["line"], case["call_anchor"]["column"])
        )
        row = next(
            b
            for b in report["bindings"]
            if b["application_id"] == site["application_id"]
        )
        consumer = row.get("alias_flow", {}).get("consumer_reference")
        reference = (
            {"name": consumer["name"], "state": consumer["state"]} if consumer else None
        )
        observed = {k: row[k] for k in ("status", "reason", "stop")}
        observed["reference"] = reference
        results.append(
            {
                "id": run_id,
                "agrees": observed == ref[run_id],
                "observed": observed,
                "reference": ref[run_id],
            }
        )
print(
    json.dumps(
        {
            "binary_sha256": hashlib.sha256(binary_path.read_bytes()).hexdigest(),
            "results": results,
        },
        indent=2,
    )
)
if not all(r["agrees"] for r in results):
    raise SystemExit("Rust and Python reference outcomes differ")
