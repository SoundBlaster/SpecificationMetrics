"""Optional pinned external metrics for an immutable application-source cohort.

No application imports or execution. stdout contains exactly one JSON object.
"""

import argparse
import json
import subprocess
import tempfile
from importlib.metadata import version
from pathlib import Path


def complexity(root):
    from complexipy import code_complexity
    from radon.complexity import cc_visit
    from radon.raw import analyze

    versions = {name: version(name) for name in ("radon", "complexipy")}
    if versions != {"radon": "6.0.1", "complexipy": "8.0.1"}:
        raise ValueError("expected radon==6.0.1 and complexipy==8.0.1")
    files = {}
    cc_values, cog_values = [], []
    sloc = 0
    for path in sorted(root.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        raw = analyze(source)
        blocks = []
        seen = set()

        def visit(block):
            # Classes are aggregates; count methods rather than counting both.
            if hasattr(block, "methods"):
                for method in block.methods:
                    visit(method)
            else:
                identity = (block.name, block.lineno)
                if identity in seen:
                    return
                seen.add(identity)
                blocks.append({"name": block.name, "line": block.lineno, "cc": block.complexity})
                for closure in getattr(block, "closures", []):
                    visit(closure)

        for block in cc_visit(source):
            visit(block)
        # Preserve every result by location; same-named methods must not overwrite.
        cognitive = [{"name": f.name, "line": f.line_start, "cog": f.complexity}
                     for f in code_complexity(source).functions]
        cc_values.extend(b["cc"] for b in blocks)
        cog_values.extend(b["cog"] for b in cognitive)
        sloc += raw.sloc
        files[path.relative_to(root).as_posix()] = {
            "sloc": raw.sloc, "loc": raw.loc, "cyclomatic": blocks, "cognitive": cognitive,
        }
    return {"status": "complete", "versions": versions, "language": "python",
            "summary": {"files": len(files), "sloc": sloc, "cc_sum": sum(cc_values),
                        "cc_max": max(cc_values, default=0), "cog_sum": sum(cog_values),
                        "cog_max": max(cog_values, default=0)}, "files": files,
            "limitations": "Function-level metrics as reported by the pinned tools; not lambda-complete. Other languages are not measured here."}


def duplication(root):
    with tempfile.TemporaryDirectory() as output:
        args = ["npx", "--yes", "jscpd@5.0.11", ".", "--reporters", "json",
                "--output", output, "--min-tokens", "30", "--min-lines", "3",
                "--format", "python,rust,swift", "--silent"]
        subprocess.run(args, cwd=root, check=True, capture_output=True, text=True, timeout=120)
        report = json.loads((Path(output) / "jscpd-report.json").read_text())
        total = report["statistics"]["total"]
        # Raw paths/timestamps are temporary execution details, not snapshot data.
        clones = []
        for clone in report["duplicates"]:
            entry = {key: clone[key] for key in ("format", "lines", "tokens")}
            for side in ("firstFile", "secondFile"):
                location = clone[side]
                entry[side] = {"path": (root / location["name"]).resolve().relative_to(root.resolve()).as_posix(),
                               "start": location["start"], "end": location["end"]}
            clones.append(entry)
        return {"status": "complete", "versions": {"jscpd": "5.0.11"},
                "settings": {"min_tokens": 30, "min_lines": 3},
                "summary": {"clone_pairs": total["clones"], "duplicate_lines": total["duplicatedLines"],
                            "duplicate_tokens": total["duplicatedTokens"]}, "clones": clones}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--complexity", action="store_true")
    parser.add_argument("--duplication", action="store_true")
    args = parser.parse_args()
    report = {}
    for name, enabled, action in (("python_complexity", args.complexity, complexity),
                                  ("duplication", args.duplication, duplication)):
        if not enabled:
            report[name] = {"status": "not_requested"}
            continue
        try:
            report[name] = action(args.root)
        except Exception as error:
            report[name] = {"status": "failed", "error": str(error)}
    report["status"] = "complete" if all(
        item["status"] in ("complete", "not_requested") for item in report.values()
    ) else "partial"
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
