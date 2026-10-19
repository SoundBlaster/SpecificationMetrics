"""Offline, source-pinned PR714 packets; no inference or execution entry point."""

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
RUN = ROOT / "runs/2026-10-19-specgraph-pr714-preparation-v1"
REVISION = "3ad8836b9e14c501bdfb5aeec11bdfdd65974eea"
REPOSITORY = "0al-spec/SpecGraph"
RUBRIC = ROOT / "runs/2026-10-19-codex-one-packet-preparation-v1/packet.json"
CONTRACT = "specmetrics.specgraph-pr714-preparation/v1"
SOURCE_INPUTS_SHA256 = "724cfe123e51b4e71beea10293902a7044e882954ed25320cc6b8095d5236c94"
RUBRIC_SHA256 = "8d4b8918895b4fdc22f24eb4a126b1c3530bae850dfde12617b1e5650488743a"
CASES = (
    ("D01", "next_sequential_spec_id", 6313, 6321),
    ("D02", "reserve_child_materialization_spec_id/selection", 6417, 6427),
    ("D03", "load_spec_id_policy/alias_validation", 6273, 6298),
    ("D04", "parse_namespaced_spec_id", 6245, 6249),
)
FUNCTIONS = (
    "parse_namespaced_spec_id", "load_spec_id_policy", "next_sequential_spec_id",
    "reserve_child_materialization_spec_id", "all_reserved_child_spec_ids",
    "pending_review_reserved_spec_ids", "load_spec_id_reservations", "spec_id_from_relpath",
)
TESTS = (
    "test_spec_id_policy_default_prefix_and_namespaced_allocation",
    "test_spec_id_policy_aliases_retire_both_alias_ids",
    "test_spec_id_policy_skips_active_and_pending_product_reservations",
    "test_malformed_spec_id_policy_fails_closed_without_mutation",
)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(path.read_bytes())


def git(repository, *args):
    return subprocess.check_output(["git", "-C", str(repository), *args])


def collect(repository, pr):
    """Read fixed Git objects and a separately captured public PR metadata object."""
    require(pr["number"] == 714 and pr["mergeCommit"]["oid"] == REVISION
            and pr["state"] == "MERGED", "wrong historical PR")
    fragments, files = {}, {}

    def fragment(path, start, end, symbol):
        raw = git(repository, "show", f"{REVISION}:{path}")
        blob = git(repository, "rev-parse", f"{REVISION}:{path}").decode().strip()
        files[path] = dict(sha256=sha(raw), git_blob=blob)
        code = b"".join(raw.splitlines(keepends=True)[start - 1:end]).decode()
        return dict(path=path, revision=REVISION, start_line=start, end_line=end,
                    symbol=symbol, file_sha256="sha256:" + sha(raw), git_blob=blob,
                    excerpt_sha256="sha256:" + sha(code.encode()), code=code)

    for path, names in (("tools/supervisor.py", FUNCTIONS), ("tests/test_supervisor.py", TESTS)):
        raw = git(repository, "show", f"{REVISION}:{path}").decode()
        nodes = {node.name: node for node in ast.parse(raw).body if isinstance(node, ast.FunctionDef)}
        for name in names:
            node = nodes[name]
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            fragments[name] = fragment(path, start, node.end_lineno, name)
        if path == "tools/supervisor.py":
            for name in ("NAMESPACED_SPEC_ID_PATTERN", "SPEC_ID_POLICY_PATH_NAME"):
                node = next(n for n in ast.parse(raw).body if isinstance(n, ast.Assign)
                            and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))
                fragments[name] = fragment(path, node.lineno, node.end_lineno, name)
    for case, symbol, start, end in CASES:
        fragments[case] = fragment("tools/supervisor.py", start, end, symbol)
    # Capture exactly the added operator guidance, not the entire manual.
    path = "docs/supervisor_manual.md"
    lines = git(repository, "show", f"{REVISION}:{path}").decode().splitlines()
    start = next(i for i, line in enumerate(lines, 1) if "spec-id-policy.json" in line)
    heading = max(i for i in range(1, start + 1) if lines[i - 1].startswith("#"))
    end = next((i - 1 for i in range(start + 1, len(lines) + 1) if lines[i - 1].startswith("#")), len(lines))
    fragments["manual"] = fragment(path, heading, end, "product child identity allocation guidance")
    path = "specs/nodes/SG-SPEC-0015.yaml"
    lines = git(repository, "show", f"{REVISION}:{path}").decode().splitlines()
    # Keep canonical status, acceptance, scope and its explicit runtime exclusion.
    end = next(i - 1 for i, line in enumerate(lines, 1) if line == "  terminology:")
    fragments["canonical_scope"] = fragment(path, 1, end, "SG-SPEC-0015 identity, acceptance and scope")
    license_text = git(repository, "show", f"{REVISION}:LICENSE").decode()
    notice_path = git(repository, "ls-tree", "--name-only", REVISION, "NOTICE").decode().strip()
    notice = git(repository, "show", f"{REVISION}:NOTICE").decode() if notice_path else ""
    return dict(repository=REPOSITORY, revision=REVISION, pr=pr, files=files, fragments=fragments,
                licensing=dict(license_path="LICENSE", license_text=license_text, upstream_notice=notice),
                provenance="Public PR metadata observed during preparation; Git fragments from the exact merge tree. No signed attestation.")


def context_for(packet, provider="jev-coreinfra", model="jev-1.13.0"):
    state, questions = packet["task"]["state"], packet["task"]["questions"]
    source = state["target"]["source"]
    binding = dict(repository=REPOSITORY, revision=REVISION, path=source["path"],
        start_line=source["start_line"], end_line=source["end_line"], decision_id=state["target"]["id"],
        evidence_sha256=sha(encoded(state).encode()), rubric_version=packet["rubric_version"],
        category_version="four-axis-choice-v1",
        prompt_config_sha256=sha(json.dumps(questions, sort_keys=True).encode()),
        action="assess_role", required_axes=[])
    return dict(expected=binding, expected_provider=provider, expected_model=model,
        assessment=dict(status="not_run", provider=provider, requested_model=model),
        missing_premises=[], checked_claims=[])


def expected(bundle=RUN):
    raw = (bundle / "source-inputs.json").read_bytes()
    require(sha(raw) == SOURCE_INPUTS_SHA256, "pinned source inputs changed")
    require(sha(RUBRIC.read_bytes()) == RUBRIC_SHA256, "pinned rubric changed")
    inputs, prior = json.loads(raw), load(RUBRIC)
    require(inputs["revision"] == REVISION and inputs["repository"] == REPOSITORY, "source identity")
    fragments = inputs["fragments"]
    for fragment in fragments.values():
        require(fragment["revision"] == REVISION
                and fragment["excerpt_sha256"] == "sha256:" + sha(fragment["code"].encode())
                and len(fragment["code"].splitlines()) == fragment["end_line"] - fragment["start_line"] + 1,
                "source fragment binding")
    artifacts = {"SpecGraph.LICENSE": inputs["licensing"]["license_text"].encode(),
        "SpecGraph.NOTICE": (f"Source excerpts: {REPOSITORY}, commit {REVISION}, PR #714.\n"
            "Source code/documentation excerpts are unchanged; collection and JSON packaging are new.\n"
            "The Apache-2.0 license for those excerpts is in SpecGraph.LICENSE.\n"
            + inputs["licensing"]["upstream_notice"]).encode()}
    rows = []
    for case, symbol, start, end in CASES:
        target = fragments[case]
        require((target["symbol"], target["start_line"], target["end_line"]) == (symbol, start, end), "target span")
        # Supply the relevant source dependencies in each independent task;
        # no author classifications or prior model labels are included.
        dependencies = FUNCTIONS if case in ("D01", "D02") else (
            ("load_spec_id_policy", "parse_namespaced_spec_id") if case == "D03" else ())
        test_names = TESTS if case in ("D01", "D02") else (
            (TESTS[1], TESTS[3]) if case == "D03" else (TESTS[0],))
        supports = [dict(source=fragments[name]) for name in dependencies
                    if fragments[name]["code"] != target["code"]]
        supports += [dict(source=fragments[name]) for name in
                     ("NAMESPACED_SPEC_ID_PATTERN", "SPEC_ID_POLICY_PATH_NAME")]
        state = dict(architecture_profile=copy.deepcopy(prior["task"]["state"]["architecture_profile"]),
            evaluation_scope=dict(repository=REPOSITORY, revision=REVISION,
                authority="proposals_only", semantic_coverage="bounded_selected_decisions",
                intent_documents_supplied=True, repository_ownership_search_complete=False,
                execution_history="fresh_context_per_target_no_previous_answers"),
            target=dict(id=f"specgraph-pr714-{case}", source=target,
                boundary="Classify the exact target/source span. Surrounding function and effects are context, not part of that span."),
            pr_context=dict(number=714, title=inputs["pr"]["title"], body=inputs["pr"]["body"],
                url=inputs["pr"]["url"], authority="historical_PR_description_not_canonical_approval"),
            supplied_documents=[dict(authority="operator_documentation", source=fragments["manual"]),
                dict(authority="canonical_specification_scope_not_exact_runtime_rule_ownership", source=fragments["canonical_scope"])],
            dependency_context=supports,
            characterization=[dict(source=fragments[name]) for name in test_names],
            known_limits=["Tests are source witnesses; no test execution is claimed by this packet.",
                "No repository-wide ownership or configured formatter/linter search is supplied; unknown is not absence.",
                "File lock, JSON reader/writer and clock implementation bodies are outside the supplied decision scope.",
                "The cited canonical spec supplies delegation context; its runtime implementation is explicitly out of scope."])
        packet = dict(schema_version=1, semantic_instructions=prior["semantic_instructions"],
            source_revision=REVISION, rubric_version=prior["rubric_version"],
            task=dict(state=state, questions=copy.deepcopy(prior["task"]["questions"])))
        payload = (encoded(packet) + "\n").encode()
        require(len(payload) <= 65536, "packet exceeds existing CLI input limit")
        artifacts[f"{case}.packet.json"] = payload
        artifacts[f"{case}.context.json"] = (encoded(context_for(packet)) + "\n").encode()
        rows.append(dict(id=case, decision_id=state["target"]["id"], symbol=symbol,
                         start_line=start, end_line=end, packet_bytes=len(payload),
                         state_bytes=len(encoded(state).encode()),
                         packet_sha256=sha(payload)))
    plan = dict(contract=CONTRACT, repository=REPOSITORY, revision=REVISION, source_pr=714, cases=rows,
        source_inputs_sha256=SOURCE_INPUTS_SHA256, rubric_source=str(RUBRIC.relative_to(ROOT)),
        rubric_source_sha256=sha(RUBRIC.read_bytes()),
        authorization=dict(inference_authorized=False, hosted_requests=0, new_sol_calls=0),
        proposed_future_scope=dict(first_stage_batches=4, questions_per_batch=4, max_conditional_reviews=4,
            primary_provider="jev-coreinfra", primary_model="jev-1.13.0", action="assess_role",
            live_dispatch_preparation="Required separately: exact wire, SDK/config/producer pins, transport limits, lease and explicit authorization."),
        reference_status="not_independently_labeled_not_accuracy_benchmark",
        automatic_fact_acceptance=False, metric_effect="none", write_authority=False)
    artifacts["plan.json"] = (encoded(plan) + "\n").encode()
    return artifacts


def freeze(bundle=RUN):
    artifacts = expected(bundle)
    require(not any((bundle / name).exists() for name in [*artifacts, "preparation-receipt.json"]), "refuse to overwrite preparation")
    for name, raw in artifacts.items():
        (bundle / name).write_bytes(raw)
    receipt = dict(contract=CONTRACT, hosted_requests=0, inference_authorized=False,
        producer_sha256=sha(Path(__file__).read_bytes()),
        files_sha256={name: sha(raw) for name, raw in artifacts.items()},
        source_inputs_sha256=SOURCE_INPUTS_SHA256)
    (bundle / "preparation-receipt.json").write_text(encoded(receipt) + "\n")
    return verify(bundle)


def verify(bundle=RUN, *, binary=None, repository=None):
    artifacts = expected(bundle)
    require({p.name for p in bundle.iterdir()} == {*artifacts, "source-inputs.json", "preparation-receipt.json", "README.md"}, "preparation inventory")
    for name, raw in artifacts.items():
        require((bundle / name).read_bytes() == raw, f"prepared artifact differs: {name}")
    require(load(bundle / "preparation-receipt.json") == dict(contract=CONTRACT, hosted_requests=0,
        inference_authorized=False, producer_sha256=sha(Path(__file__).read_bytes()),
        files_sha256={name: sha(raw) for name, raw in artifacts.items()}, source_inputs_sha256=SOURCE_INPUTS_SHA256), "preparation receipt")
    if repository:
        inputs = load(bundle / "source-inputs.json")
        for fragment in inputs["fragments"].values():
            raw = git(repository, "show", f'{REVISION}:{fragment["path"]}')
            excerpt = b"".join(raw.splitlines(keepends=True)[fragment["start_line"] - 1:fragment["end_line"]]).decode()
            require("sha256:" + sha(raw) == fragment["file_sha256"] and excerpt == fragment["code"], "historical Git source differs")
    if binary:
        with tempfile.TemporaryDirectory(prefix="pr714-offline-") as td:
            for case, *_ in CASES:
                output = Path(td) / f"{case}.prepared.json"
                subprocess.run([str(Path(binary).resolve()), "prepare-classification", "--packet", str(bundle / f"{case}.packet.json"),
                    "--config", str(ROOT.parents[1] / "configs/codex-categorical.example.toml"), "--output", str(output)],
                    check=True, capture_output=True, timeout=30)
                require(load(output)["packet"] == load(bundle / f"{case}.packet.json"), "CLI packet changed")
    return dict(status="verified_offline", cases=4, hosted_requests=0, inference_authorized=False,
                cli_preparation_checked=binary is not None, git_source_checked=repository is not None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "verify"))
    parser.add_argument("--bundle", type=Path, default=RUN)
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--repository", type=Path)
    args = parser.parse_args()
    print(encoded(freeze(args.bundle) if args.action == "freeze" else
                  verify(args.bundle, binary=args.binary, repository=args.repository)))
