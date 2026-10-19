"""Offline PR714 v2: preserve context without repeating the selected source span."""

import argparse
import copy
from pathlib import Path
import subprocess
import tempfile

import prepare_specgraph_pr714_v1 as prior
from prepare_specgraph_pr714_v1 import CASES, ROOT, context_for, encoded, load, require, sha

RUN = ROOT / "runs/2026-10-19-specgraph-pr714-preparation-v2"
CONTRACT = "specmetrics.specgraph-pr714-preparation/v2"


def overlaps(left, right):
    return (left["path"] == right["path"] and left["revision"] == right["revision"]
            and max(left["start_line"], right["start_line"]) <= min(left["end_line"], right["end_line"]))


def surrounding(source, target):
    """Subtract target coordinates, keeping exact bytes/absolute spans around it."""
    if not overlaps(source, target):
        return [copy.deepcopy(source)]
    result = []
    for start, end in ((source["start_line"], min(source["end_line"], target["start_line"] - 1)),
                       (max(source["start_line"], target["end_line"] + 1), source["end_line"])):
        if start <= end:
            code = "".join(source["code"].splitlines(keepends=True)[start-source["start_line"]:end-source["start_line"]+1])
            result.append(dict(source, start_line=start, end_line=end, code=code,
                symbol=f'{source["symbol"]}[{start}:{end}]', excerpt_sha256="sha256:" + sha(code.encode())))
    return result


def require_nonoverlap(packet):
    state = packet["task"]["state"]
    target = state["target"]["source"]
    require(all(not overlaps(entry["source"], target) for entry in state["dependency_context"]),
            "dependency fragment overlaps target")


def expected():
    prior.verify()
    previous = prior.expected()
    artifacts = {name: previous[name] for name in ("SpecGraph.LICENSE", "SpecGraph.NOTICE")}
    rows = []
    for case, symbol, start, end in CASES:
        packet = load(prior.RUN / f"{case}.packet.json")
        state = packet["task"]["state"]
        target = state["target"]["source"]
        state["dependency_context"] = [dict(source=piece)
            for entry in state["dependency_context"] for piece in surrounding(entry["source"], target)]
        require_nonoverlap(packet)
        payload = (encoded(packet) + "\n").encode()
        require(len(payload) <= 65536, "packet exceeds existing CLI input limit")
        artifacts[f"{case}.packet.json"] = payload
        artifacts[f"{case}.context.json"] = (encoded(context_for(packet)) + "\n").encode()
        rows.append(dict(id=case, decision_id=state["target"]["id"], symbol=symbol,
            start_line=start, end_line=end, packet_bytes=len(payload), packet_sha256=sha(payload),
            state_bytes=len(encoded(state).encode()), target_overlap_count=0))
    plan = load(prior.RUN / "plan.json")
    plan.update(contract=CONTRACT, cases=rows,
        derivation=dict(preparation=str(prior.RUN.relative_to(ROOT)),
            receipt_sha256=sha((prior.RUN / "preparation-receipt.json").read_bytes()),
            producer_sha256=sha(Path(prior.__file__).read_bytes())),
        correction="Subtract exact target path/revision/line interval from dependency context; preserve non-overlapping surroundings.")
    artifacts["plan.json"] = (encoded(plan) + "\n").encode()
    return artifacts


def receipt(artifacts):
    return dict(contract=CONTRACT, hosted_requests=0, inference_authorized=False,
        producer_sha256=sha(Path(__file__).read_bytes()),
        parent_receipt_sha256=sha((prior.RUN / "preparation-receipt.json").read_bytes()),
        files_sha256={name: sha(raw) for name, raw in artifacts.items()})


def freeze(bundle=RUN):
    artifacts = expected()
    require({p.name for p in bundle.iterdir()} == {"README.md"}, "refuse to overwrite preparation")
    for name, raw in {**artifacts, "preparation-receipt.json": (encoded(receipt(artifacts)) + "\n").encode()}.items():
        with (bundle / name).open("xb") as stream:
            stream.write(raw)
    return verify(bundle)


def verify(bundle=RUN, *, binary=None):
    artifacts = expected()
    require({p.name for p in bundle.iterdir()} == {*artifacts, "preparation-receipt.json", "README.md"}, "preparation inventory")
    for case, *_ in CASES:
        require_nonoverlap(load(bundle / f"{case}.packet.json"))
    for name, raw in artifacts.items():
        require((bundle / name).read_bytes() == raw, f"prepared artifact differs: {name}")
    require(load(bundle / "preparation-receipt.json") == receipt(artifacts), "preparation receipt")
    if binary:
        with tempfile.TemporaryDirectory(prefix="pr714-v2-offline-") as td:
            for case, *_ in CASES:
                output = Path(td) / f"{case}.prepared.json"
                subprocess.run([str(Path(binary).resolve()), "prepare-classification", "--packet", str(bundle / f"{case}.packet.json"),
                    "--config", str(ROOT.parents[1] / "configs/codex-categorical.example.toml"), "--output", str(output)],
                    check=True, capture_output=True, timeout=30)
                require(load(output)["packet"] == load(bundle / f"{case}.packet.json"), "CLI packet changed")
    return dict(status="verified_offline", cases=4, target_overlap_count=0, hosted_requests=0,
                inference_authorized=False, cli_preparation_checked=binary is not None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "verify"))
    parser.add_argument("--bundle", type=Path, default=RUN)
    parser.add_argument("--binary", type=Path)
    args = parser.parse_args()
    print(encoded(freeze(args.bundle) if args.action == "freeze" else verify(args.bundle, binary=args.binary)))
