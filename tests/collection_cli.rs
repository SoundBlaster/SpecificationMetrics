use std::fs;
use std::path::Path;
use std::process::Command;

use serde_json::Value;
use tempfile::tempdir;

fn run(args: &[&str]) -> std::process::Output {
    Command::new(env!("CARGO_BIN_EXE_specification-metrics"))
        .args(args)
        .output()
        .unwrap()
}

#[test]
fn collect_compare_and_history_keep_primary_counters() {
    let dir = tempdir().unwrap();
    let root = dir.path();
    let config = root.join("metrics.toml");
    let source = root.join("policy.py");
    let before = root.join("before.json");
    let after = root.join("after.json");
    let store = root.join("metrics.sqlite");
    fs::write(
        &config,
        "schema_version=1\nproject='example'\nroot='.'\nincludes=['policy.py']\n",
    )
    .unwrap();
    fs::write(&source, "if ready: pass\nif allowed: pass\n").unwrap();
    let collect = |output: &std::path::Path| {
        run(&[
            "collect",
            "--config",
            config.to_str().unwrap(),
            "--output",
            output.to_str().unwrap(),
            "--store",
            store.to_str().unwrap(),
            "--require-complete",
        ])
    };
    assert!(collect(&before).status.success());
    assert!(collect(&before).status.success()); // same snapshot, not a new timestamp
    fs::write(
        &source,
        "ready = PredicateSpec(lambda value: value)\nif allowed: pass\n",
    )
    .unwrap();
    assert!(collect(&after).status.success());
    let delta = run(&["compare", before.to_str().unwrap(), after.to_str().unwrap()]);
    assert!(
        delta.status.success(),
        "{}",
        String::from_utf8_lossy(&delta.stderr)
    );
    let delta: Value = serde_json::from_slice(&delta.stdout).unwrap();
    assert_eq!(delta["primary"]["remaining_opportunities"]["delta"], -1);
    assert_eq!(delta["primary"]["specification_definitions"]["delta"], 1);
    assert_eq!(delta["supplementary"]["duplication"]["delta"], Value::Null);
    let history = run(&["collection-history", "--store", store.to_str().unwrap()]);
    let history: Value = serde_json::from_slice(&history.stdout).unwrap();
    assert_eq!(history.as_array().unwrap().len(), 2);
    assert_eq!(
        history[0]["report"]["primary"]["remaining_opportunities"],
        1
    );
    let mut b: Value = serde_json::from_slice(&fs::read(&before).unwrap()).unwrap();
    let mut a: Value = serde_json::from_slice(&fs::read(&after).unwrap()).unwrap();
    b["supplementary"]["python_complexity"] = serde_json::json!({
        "status":"complete", "versions":{"radon":"6.0.1"}, "summary":{"cc_sum":10}
    });
    a["supplementary"]["python_complexity"] = serde_json::json!({
        "status":"complete", "versions":{"radon":"6.0.1"}, "summary":{"cc_sum":12}
    });
    fs::write(&before, serde_json::to_vec(&b).unwrap()).unwrap();
    fs::write(&after, serde_json::to_vec(&a).unwrap()).unwrap();
    let delta: Value = serde_json::from_slice(
        &run(&["compare", before.to_str().unwrap(), after.to_str().unwrap()]).stdout,
    )
    .unwrap();
    assert_eq!(
        delta["supplementary"]["python_complexity"]["delta"]["cc_sum"],
        2.0
    );
    a["supplementary"]["python_complexity"]["versions"]["radon"] = "other".into();
    fs::write(&after, serde_json::to_vec(&a).unwrap()).unwrap();
    let delta: Value = serde_json::from_slice(
        &run(&["compare", before.to_str().unwrap(), after.to_str().unwrap()]).stdout,
    )
    .unwrap();
    assert_eq!(
        delta["supplementary"]["python_complexity"]["status"],
        "not_comparable"
    );
    assert_eq!(
        delta["supplementary"]["python_complexity"]["delta"],
        Value::Null
    );
    // A policy change invalidates comparison even if its raw counts happen to match.
    fs::write(
        &config,
        "schema_version=1\nproject='different'\nroot='.'\nincludes=['policy.py']\n",
    )
    .unwrap();
    assert!(collect(&after).status.success());
    assert!(
        !run(&["compare", before.to_str().unwrap(), after.to_str().unwrap()])
            .status
            .success()
    );
}

#[test]
fn missing_optional_tool_never_becomes_a_zero_and_strict_mode_does_not_store() {
    let dir = tempdir().unwrap();
    let config = dir.path().join("metrics.toml");
    let output = dir.path().join("report.json");
    let store = dir.path().join("metrics.sqlite");
    fs::write(dir.path().join("policy.py"), "if ready: pass\n").unwrap();
    fs::write(&config, "schema_version=1\nproject='example'\nroot='.'\nincludes=['policy.py']\n[supplementary]\npython_complexity=true\npython='missing-metrics-python'\n").unwrap();
    let result = run(&[
        "collect",
        "--config",
        config.to_str().unwrap(),
        "--output",
        output.to_str().unwrap(),
        "--store",
        store.to_str().unwrap(),
        "--require-complete",
    ]);
    assert!(!result.status.success());
    assert!(!store.exists());
    let report: Value = serde_json::from_slice(&fs::read(output).unwrap()).unwrap();
    assert_eq!(report["primary"]["remaining_opportunities"], 1);
    assert_eq!(report["status"], "partial");
    assert_eq!(report["supplementary"]["status"], "failed");
}

#[test]
fn provisional_discovery_and_config_typos_are_explicit() {
    let dir = tempdir().unwrap();
    let config = dir.path().join("metrics.toml");
    fs::write(dir.path().join("policy.py"), "if ready: pass\n").unwrap();
    fs::write(&config, "schema_version=1\nproject='example'\nroot='.'\n").unwrap();
    let result = run(&["collect", "--config", config.to_str().unwrap()]);
    assert!(result.status.success());
    let report: Value = serde_json::from_slice(&result.stdout).unwrap();
    assert_eq!(report["status"], "provisional");
    fs::write(
        &config,
        "schema_version=1\nproject='example'\nroot='.'\ninclude=['policy.py']\n",
    )
    .unwrap();
    assert!(
        !run(&["collect", "--config", config.to_str().unwrap()])
            .status
            .success()
    );
}

#[test]
fn bare_output_and_store_names_work_in_the_current_directory() {
    let dir = tempdir().unwrap();
    fs::write(dir.path().join("policy.py"), "if ready: pass\n").unwrap();
    fs::write(
        dir.path().join("metrics.toml"),
        "schema_version=1\nproject='example'\nroot='.'\nincludes=['policy.py']\n",
    )
    .unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_specification-metrics"))
        .current_dir(dir.path())
        .args([
            "collect",
            "--config",
            "metrics.toml",
            "--output",
            "report.json",
            "--store",
            "metrics.sqlite",
        ])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(dir.path().join("report.json").is_file());
    assert!(dir.path().join("metrics.sqlite").is_file());
}

#[test]
fn pr_locations_match_snapshots_and_abstain_for_duplicate_or_unverified_sites() {
    let dir = tempdir().unwrap();
    let repo = dir.path();
    let git = |args: &[&str]| {
        let output = Command::new("git")
            .current_dir(repo)
            .args(args)
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        String::from_utf8(output.stdout).unwrap().trim().to_owned()
    };
    git(&["init", "-q"]);
    let src = repo.join("pkg");
    fs::create_dir(&src).unwrap();
    let file = src.join("a (1).py");
    let config = repo.join("metrics.toml");
    fs::write(
        &config,
        "schema_version=1\nproject='org/repo'\nroot='pkg'\nincludes=['a (1).py']\n",
    )
    .unwrap();
    let collect = |out: &Path| {
        let result = run(&[
            "collect",
            "--candidate-locations",
            "--config",
            config.to_str().unwrap(),
            "--output",
            out.to_str().unwrap(),
        ]);
        assert!(
            result.status.success(),
            "{}",
            String::from_utf8_lossy(&result.stderr)
        );
    };
    let commit = || {
        git(&["add", "--", "pkg"]);
        git(&[
            "-c",
            "user.name=test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "snapshot",
        ]);
        git(&["rev-parse", "HEAD"])
    };
    let base = repo.join("b.json");
    let head = repo.join("h.json");
    let compare = |more: &[&str]| {
        let mut args = vec!["compare", base.to_str().unwrap(), head.to_str().unwrap()];
        args.extend_from_slice(more);
        let output = run(&args);
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        String::from_utf8(output.stdout).unwrap()
    };
    fs::write(
        &file,
        "if old: pass\nif same: pass\nif same: pass\nif moved: pass\n",
    )
    .unwrap();
    let old = commit();
    collect(&base);
    fs::write(&file, "if moved: pass\nif same: pass\nif new: pass\nRULE = PredicateSpec(lambda v: 1 if v else 0)\n").unwrap();
    let new = commit();
    collect(&head);
    let diff: Value = serde_json::from_str(&compare(&[])).unwrap();
    let ch = &diff["opportunity_changes"];
    assert_eq!(ch["status"], "complete");
    assert_eq!(ch["added"].as_array().unwrap().len(), 1);
    assert_eq!(ch["removed"].as_array().unwrap().len(), 1);
    assert_eq!(ch["added"][0]["line"], 3);
    assert_eq!(ch["added"][0]["column"], 1);
    assert_eq!(ch["ambiguous"][0]["before"].as_array().unwrap().len(), 2);
    assert_eq!(ch["ambiguous"][0]["after"].as_array().unwrap().len(), 1);
    assert_eq!(diff["primary"]["remaining_opportunities"]["delta"], -1);
    let md = compare(&["--github-markdown", "org/repo"]);
    assert!(md.contains("ambiguous groups 1 (contribution to ΔU: -1)"));
    assert!(md.contains("Total ΔU: 1 − 1 + (-1) = -1."));
    assert!(md.contains(&format!("/blob/{new}/pkg/a%20%281%29.py#L3")));
    assert!(md.contains(&format!("/blob/{old}/pkg/a%20%281%29.py#L1")));
    // A nonzero total must not be confused with zero ambiguous contribution
    // (the shape of the real SpecGraph PR #852 report: 23 added, 2 removed).
    fs::write(&file, "if removed_a: pass\nif removed_b: pass\n").unwrap();
    commit();
    collect(&base);
    let additions: String = (0..23).map(|i| format!("if added_{i}: pass\n")).collect();
    fs::write(&file, additions).unwrap();
    let new = commit();
    collect(&head);
    let md = compare(&["--github-markdown", "org/repo"]);
    assert!(md.contains("Remaining opportunities (U) · 2 → 23 (+21)"));
    assert!(md.contains("Added 23, removed 2, ambiguous groups 0 (contribution to ΔU: +0)"));
    assert!(md.contains("Total ΔU: 23 − 2 + (+0) = +21."));
    assert_eq!(md.lines().filter(|line| line.starts_with("- ")).count(), 20);
    assert!(md.contains("More locations in the JSON comparison."));
    fs::write(&file, "if dirty: pass\n").unwrap();
    collect(&head);
    let dirty = compare(&["--github-markdown", "org/repo"]);
    assert!(dirty.contains("revision link unavailable"));
    assert!(!dirty.contains(&format!("/blob/{new}/")));
    let mut legacy: Value = serde_json::from_slice(&fs::read(&base).unwrap()).unwrap();
    legacy.as_object_mut().unwrap().remove("opportunity_sites");
    fs::write(&base, serde_json::to_vec(&legacy).unwrap()).unwrap();
    assert!(compare(&["--github-markdown", "org/repo"]).contains("missing_inventory"));
}
