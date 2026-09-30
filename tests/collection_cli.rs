use std::fs;
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
