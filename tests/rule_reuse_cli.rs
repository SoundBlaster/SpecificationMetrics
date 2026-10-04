use serde_json::Value;
use std::{fs, process::Command};

fn run(args: &[&str]) -> std::process::Output {
    Command::new(env!("CARGO_BIN_EXE_specification-metrics"))
        .args(args)
        .output()
        .unwrap()
}
fn git(root: &std::path::Path, args: &[&str]) -> String {
    let result = Command::new("git")
        .arg("-C")
        .arg(root)
        .args(args)
        .output()
        .unwrap();
    assert!(result.status.success());
    String::from_utf8(result.stdout).unwrap().trim().into()
}
fn commit(root: &std::path::Path) -> String {
    git(root, &["add", "."]);
    git(
        root,
        &[
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
    );
    git(root, &["rev-parse", "HEAD"])
}
#[test]
fn strict_gate_emits_and_stores_failed_report_and_does_not_read_working_tree() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path();
    git(root, &["init", "-q"]);
    fs::create_dir(root.join("tools")).unwrap();
    fs::write(root.join("tools/spec.py"),"from specification_core import PredicateSpec\nPOLICY=PredicateSpec(lambda facts: facts.allowed is True)\n").unwrap();
    fs::write(root.join("tools/caller.py"), "pass\n").unwrap();
    let base = commit(root);
    let fingerprint = run(&[
        "fingerprint-rule",
        root.to_str().unwrap(),
        "--path",
        "tools/spec.py",
        "--symbol",
        "POLICY",
    ]);
    assert!(fingerprint.status.success());
    let value: Value = serde_json::from_slice(&fingerprint.stdout).unwrap();
    let catalog = root.join("catalog.toml");
    fs::write(&catalog,format!("schema_version=1\nproject='fixture'\n[[rules]]\nid='policy'\nbounded_context='publication'\npaths=['tools']\ncanonical_path='tools/spec.py'\ncanonical_symbol='POLICY'\ncanonical_digest='{}'\n",value["digest"].as_str().unwrap())).unwrap();
    fs::write(
        root.join("tools/caller.py"),
        "if facts.allowed is True:\n    publish()\n",
    )
    .unwrap();
    commit(root);
    // A clean working-tree buffer cannot hide a committed copy.
    fs::write(root.join("tools/caller.py"), "pass\n").unwrap();
    let output = root.join("report.json");
    let store = root.join("metrics.sqlite");
    let args = [
        "check-rule-reuse",
        root.to_str().unwrap(),
        "--catalog",
        catalog.to_str().unwrap(),
        "--base",
        &base,
        "--output",
        output.to_str().unwrap(),
        "--store",
        store.to_str().unwrap(),
        "--strict",
    ];
    let result = run(&args);
    assert!(!result.status.success());
    let report: Value = serde_json::from_slice(&fs::read(&output).unwrap()).unwrap();
    assert_eq!(report["status"], "complete");
    assert_eq!(report["new_reimplementations"], 1);
    let history = run(&["rule-reuse-history", "--store", store.to_str().unwrap()]);
    assert!(history.status.success());
    let history: Value = serde_json::from_slice(&history.stdout).unwrap();
    assert_eq!(history.as_array().unwrap().len(), 1);
    // Report-only mode preserves findings and returns success.
    assert!(run(&args[..args.len() - 1]).status.success());
    // Hosted classification needs explicit opt-in, even with no requests due.
    let denied = run(&[
        "check-rule-reuse",
        root.to_str().unwrap(),
        "--catalog",
        catalog.to_str().unwrap(),
        "--base",
        &base,
        "--classify-near-matches",
    ]);
    assert!(!denied.status.success());
}

#[test]
fn review_template_warning_passes_strict_and_is_stored() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path();
    git(root, &["init", "-q"]);
    fs::create_dir(root.join("tools")).unwrap();
    fs::write(root.join("tools/spec.py"), "from specification_core import PredicateSpec\nPOLICY=PredicateSpec(lambda facts: facts.reviewed_digest == facts.requested_digest)\n").unwrap();
    fs::write(root.join("tools/caller.py"), "pass\n").unwrap();
    let base = commit(root);
    let fingerprint = run(&[
        "fingerprint-rule",
        root.to_str().unwrap(),
        "--path",
        "tools/spec.py",
        "--symbol",
        "POLICY",
    ]);
    assert!(fingerprint.status.success());
    let value: Value = serde_json::from_slice(&fingerprint.stdout).unwrap();
    let catalog = root.join("catalog.toml");
    fs::write(&catalog,format!("schema_version=1\nproject='fixture'\n[[rules]]\nid='policy'\nbounded_context='publication'\npaths=['tools']\ncanonical_path='tools/spec.py'\ncanonical_symbol='POLICY'\ncanonical_digest='{}'\n[[rules.review_templates]]\nid='partial'\nexpression=\"draft['title'] == document['title']\"\nrenameable_identifiers=['draft','document']\nsource_url='https://github.com/example/repo/commit/123'\n",value["digest"].as_str().unwrap())).unwrap();
    fs::write(
        root.join("tools/caller.py"),
        "if draft['title'] == document['title']:\n    publish()\n",
    )
    .unwrap();
    commit(root);
    let output = root.join("report.json");
    let store = root.join("metrics.sqlite");
    let result = run(&[
        "check-rule-reuse",
        root.to_str().unwrap(),
        "--catalog",
        catalog.to_str().unwrap(),
        "--base",
        &base,
        "--output",
        output.to_str().unwrap(),
        "--store",
        store.to_str().unwrap(),
        "--strict",
    ]);
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    let report: Value = serde_json::from_slice(&fs::read(output).unwrap()).unwrap();
    assert_eq!(report["new_reimplementations"], 0);
    assert_eq!(report["new_near_matches"], 1);
    assert_eq!(report["findings"][0]["match_basis"], "review_template");
    let history = run(&["rule-reuse-history", "--store", store.to_str().unwrap()]);
    assert!(history.status.success());
    let snapshots: Value = serde_json::from_slice(&history.stdout).unwrap();
    assert_eq!(snapshots[0]["report"]["new_near_matches"], 1);
}
