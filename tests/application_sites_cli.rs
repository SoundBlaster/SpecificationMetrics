use serde_json::Value;
use std::{fs, path::Path, process::Command};

fn invoke(command: &str, root: &Path, manifest: &Path, extra: &[&str]) -> std::process::Output {
    Command::new(env!("CARGO_BIN_EXE_specification-metrics"))
        .arg(command)
        .arg(root)
        .arg("--scope-manifest")
        .arg(manifest)
        .args(extra)
        .output()
        .unwrap()
}

#[test]
fn advisory_report_shares_source_identity_and_preserves_measure_output() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path();
    let manifest = root.join("scope.toml");
    fs::write(
        &manifest,
        "schema_version = 1\n[[source_sets]]\nrole = 'application'\npaths = ['app.py']\n",
    )
    .unwrap();
    let source = "from specification_core import PredicateSpec\nREADY = PredicateSpec(lambda c: c.ready)\ndef run(c):\n    if READY.is_satisfied_by(c): return True\n    if unknown.is_satisfied_by(c): return False\n";
    fs::write(root.join("app.py"), source).unwrap();
    let before = invoke("measure", root, &manifest, &["--require-complete"]);
    assert!(
        before.status.success(),
        "{}",
        String::from_utf8_lossy(&before.stderr)
    );
    let output_path = root.join("applications.json");
    let output = invoke(
        "application-sites",
        root,
        &manifest,
        &["--output", output_path.to_str().unwrap()],
    );
    assert!(output.status.success());
    assert!(output.stdout.is_empty());
    assert!(output.stderr.is_empty());
    let report: Value = serde_json::from_slice(&fs::read(output_path).unwrap()).unwrap();
    assert_eq!(report["direct_application"], 1);
    assert_eq!(report["unresolved_call"], 1);
    assert_eq!(report["provisional"], false);
    assert_eq!(report["metric_effect"], "none");
    let raw: Value = serde_json::from_slice(&before.stdout).unwrap();
    assert_eq!(raw["remaining_opportunities"], 2);
    assert_eq!(raw["source_digest"], report["source_digest"]);
    assert_eq!(
        raw["scope_manifest_digest"],
        report["scope_manifest_digest"]
    );
    assert_eq!(
        before.stdout,
        invoke("measure", root, &manifest, &["--require-complete"]).stdout
    );
    assert_eq!(fs::read_to_string(root.join("app.py")).unwrap(), source);
}
