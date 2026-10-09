use serde_json::Value;
use std::{fs, process::Command};

fn extract(root: &std::path::Path, extra: &[&str]) -> std::process::Output {
    Command::new(env!("CARGO_BIN_EXE_specification-metrics"))
        .args([
            "extract-decision-target",
            root.to_str().unwrap(),
            "--path",
            "case.py",
            "--line",
            "2",
            "--column",
            "5",
            "--syntax-kind",
            "return_statement",
            "--select",
            "value",
        ])
        .args(extra)
        .output()
        .unwrap()
}

#[test]
fn cli_exports_exact_expression_without_mutating_sources_or_making_provider_calls() {
    let dir = tempfile::tempdir().unwrap();
    let source = "def ready(x):\n    return x.ready and x.allowed\n";
    fs::write(dir.path().join("case.py"), source).unwrap();
    let output = extract(dir.path(), &[]);
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let report: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(report["expression"]["code"], "x.ready and x.allowed");
    assert_eq!(report["ownership_status"], "unknown");
    assert_eq!(report["metric_effect"], "none");
    let expected = report["source_digest"].as_str().unwrap();
    assert!(
        extract(dir.path(), &["--expected-source-digest", expected])
            .status
            .success()
    );
    fs::write(dir.path().join("case.py"), source.to_owned() + "# drift\n").unwrap();
    let stale = extract(dir.path(), &["--expected-source-digest", expected]);
    assert!(!stale.status.success());
    assert!(stale.stdout.is_empty());
    assert!(String::from_utf8_lossy(&stale.stderr).contains("source digest mismatch"));
    assert_eq!(fs::read_dir(dir.path()).unwrap().count(), 1);
}
