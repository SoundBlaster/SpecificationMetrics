#!/usr/bin/env python3
"""Extract exact, immutable Git source excerpts; never import or execute them."""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).parent
CORPUS = ROOT / "corpus"
REPOSITORY = "https://github.com/0al-spec/SpecGraph"


def digest(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args]).decode("utf-8")


def declaration_name(node):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        return getattr(node.targets[0], "id", None)
    if isinstance(node, ast.AnnAssign):
        return getattr(node.target, "id", None)
    return None


def excerpt(repo, revision, path, selector):
    source = git(repo, "show", f"{revision}:{path}")
    tree = ast.parse(source)
    declarations = {declaration_name(n): n for n in tree.body if declaration_name(n)}
    symbol = selector["symbol"]
    node = declarations[symbol]
    if "node_kind" in selector:
        kind = getattr(ast, selector["node_kind"])
        matches = [n for n in ast.walk(node) if isinstance(n, kind)
                   and selector["contains"] in ast.get_source_segment(source, n)]
        if len(matches) != 1:
            raise ValueError(f"{revision}:{path}:{selector}: expected one node, got {len(matches)}")
        node = matches[0]
    return record(node, revision, path, symbol, source), source


def record(node, revision, path, symbol, source):
    start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    code = "".join(source.splitlines(keepends=True)[start - 1:node.end_lineno])
    return {
        "revision": revision, "path": path, "symbol": symbol,
        "start_line": start, "end_line": node.end_lineno,
        "file_sha256": digest(source), "excerpt_sha256": digest(code),
        "url": f"{REPOSITORY}/blob/{revision}/{path}#L{start}-L{node.end_lineno}",
        "code": code,
    }


def build(repo):
    selection = json.loads((CORPUS / "selection.json").read_text())
    cases = []
    for item in selection["cases"]:
        revision = item["revision"]
        if git(repo, "rev-parse", revision).strip() != revision:
            raise ValueError("source revisions must be full immutable commit SHAs")
        site, source = excerpt(repo, revision, item["path"], item["selector"])
        supporting = [record(n, revision, item["path"], f"import@{n.lineno}", source)
                      for n in ast.parse(source).body if isinstance(n, (ast.Import, ast.ImportFrom))]
        # Explicit selections keep the context budget reviewable and reproducible.
        for support in item.get("supporting", []):
            support_record, _ = excerpt(repo, revision, support.get("path", item["path"]),
                                        support.get("selector", {"symbol": support.get("symbol")}))
            supporting.append(support_record)
        context = {
            "candidate_id": item["id"],
            "source": {"language": "Python", "path": item["path"],
                       "symbol": item["selector"]["symbol"],
                       "construct": item.get("construct", "declaration")},
            "site": {"code": site["code"], "start_line": site["start_line"],
                     "end_line": site["end_line"]},
            "bounded_context": {
                "supporting_code": [{"path": s["path"], "symbol": s["symbol"],
                                     "code": s["code"]} for s in supporting],
                "scope": "Selected source declarations; callers and unlisted dependencies are omitted.",
                "truncated": False,
            },
        }
        encoded = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 24 * 1024:
            raise ValueError(f"{item['id']}: exceeds the 24 KiB context budget")
        cases.append({
            "description": item["id"],
            "vars": {"candidate_json": encoded,
                     "expected_opportunity": item["proposed_opportunity"],
                     "expected_concern_kind": item["proposed_concern_kind"],
                     "label_status": "pilot_hypothesis"},
            "metadata": {
                "family_id": item["family_id"], "split": "unassigned",
                "role": item["role"], "review_status": "unreviewed",
                "label_source": "agent_proposal_from_source_inspection",
                "label_rationale": item["rationale"],
                "source": {"repository": REPOSITORY, "license": "Apache-2.0",
                           "site": site, "supporting": supporting},
                "history": item.get("history"), "context_sha256": digest(encoded),
            },
            "assert": [{"type": "javascript", "value": "file://assertions/choice-probability.js",
                        "config": {"axis": axis}} for axis in ("opportunity", "concern_kind")],
        })
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    cases = build(args.repo)
    rendered = lambda data: json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    smoke = json.loads(json.dumps(next(c for c in cases if c["metadata"]["family_id"] == "workspace-allocation")))
    state = json.loads(smoke["vars"]["candidate_json"])
    state["candidate_id"] = "publication.site.069"
    smoke["vars"]["candidate_json"] = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    smoke["metadata"]["context_sha256"] = digest(smoke["vars"]["candidate_json"])
    smoke["description"] = "SpecGraph publication.site.069: exact workspace allocation source guard"
    review = {"schema_version": 1, "rubric_id": "specification_metrics.candidate.v1", "rubric_version": 1,
              "reviewer_id": None, "reviews": []}
    packet = ["# SpecGraph classification review packet", "",
              "Review source before opening proposed labels. This packet omits proposed labels, selection roles, refactoring phases, and prior diagnoses. All source is Apache-2.0; see LICENSE.SpecGraph.", ""]
    for case in cases:
        state = json.loads(case["vars"]["candidate_json"])
        site = case["metadata"]["source"]["site"]
        packet += [f"## {state['candidate_id']}", "", f"[Pinned source]({site['url']})",
                   "", "```python", state["site"]["code"].rstrip(), "```", ""]
        for support in state["bounded_context"]["supporting_code"]:
            packet += [f"Supporting declaration: `{support['path']}::{support['symbol']}`",
                       "", "```python", support["code"].rstrip(), "```", ""]
        packet += ["Opportunity: ______  Concern kind: ______", "", "Evidence / missing context: ______", ""]
        review["reviews"].append({"candidate_id": state["candidate_id"], "opportunity": None,
                                 "concern_kind": None, "rationale": None})
    artifacts = {CORPUS / "cases.json": rendered(cases), ROOT / "cases.json": rendered([smoke]),
                 CORPUS / "review.md": "\n".join(packet).rstrip() + "\n",
                 CORPUS / "review-template.json": rendered(review)}
    if args.check:
        stale = [str(path.relative_to(ROOT)) for path, data in artifacts.items() if path.read_text() != data]
        if stale:
            raise SystemExit(f"artifacts differ from pinned Git selections: {stale}")
        print("all corpus inputs match pinned Git source; no model requests made")
    else:
        for path, data in artifacts.items():
            path.write_text(data)
        print(f"wrote {len(cases)} source-grounded, unreviewed cases and review packet; no model requests made")


if __name__ == "__main__":
    main()
