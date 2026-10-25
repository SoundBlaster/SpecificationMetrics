use serde_json::Value;
use std::{fs, path::Path, process::Command};

#[test]
fn loop_enum_flow_retains_declaration_and_iteration_evidence() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path();
    let manifest = root.join("scope.toml");
    fs::write(
        &manifest,
        "schema_version = 1\n[[source_sets]]\nrole = 'application'\npaths = ['app.py']\n",
    )
    .unwrap();
    fs::write(root.join("app.py"), "from specification_core import FirstMatch\nfrom enum import Enum\nclass Choice(Enum):\n    ACCEPT = 'accept'\nRULE = FirstMatch.with_fallback((), Choice.ACCEPT)\ndef run(c):\n    for item in c:\n        value = RULE.decide(item)\n        if value.value == Choice.ACCEPT: pass\n").unwrap();
    let before = invoke("measure", root, &manifest, &["--require-complete"]);
    assert!(before.status.success());
    let typed = invoke(
        "application-sites",
        root,
        &manifest,
        &["--profile", "python-decisions-v1"],
    );
    let default = invoke("application-sites", root, &manifest, &[]);
    let flow = invoke(
        "application-sites",
        root,
        &manifest,
        &["--profile", "python-decision-flow-v1"],
    );
    assert!(flow.status.success());
    let flow: Value = serde_json::from_slice(&flow.stdout).unwrap();
    assert_eq!(flow["linked_bindings"], 1);
    assert_eq!(flow["metric_effect"], "none");
    let branch = &flow["bindings"][0]["branch"];
    assert_eq!(branch["anchor"]["line"], 9);
    assert_eq!(branch["enum_member"]["class_name"], "Choice");
    assert_eq!(branch["enum_member"]["member_name"], "ACCEPT");
    assert_eq!(branch["enum_member"]["class_anchor"]["line"], 3);
    assert_eq!(branch["enum_member"]["member_anchor"]["line"], 4);
    assert_eq!(branch["loop_anchors"][0]["line"], 7);
    assert_eq!(
        flow["applications"],
        serde_json::from_slice::<Value>(&typed.stdout).unwrap()
    );
    assert_eq!(
        before.stdout,
        invoke("measure", root, &manifest, &["--require-complete"]).stdout
    );
    assert_eq!(
        default.stdout,
        invoke("application-sites", root, &manifest, &[]).stdout
    );
}

#[test]
fn flow_links_the_scan_candidate_without_mutating_prior_profiles_or_measurement() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path();
    let manifest = root.join("scope.toml");
    fs::write(
        &manifest,
        "schema_version = 1\n[[source_sets]]\nrole = 'application'\npaths = ['app.py']\n",
    )
    .unwrap();
    fs::write(root.join("app.py"), "from specification_core import FirstMatch\nRULE = FirstMatch.with_fallback((), 'ok')\ndef run(c):\n    value = RULE.decide(c).value\n    if value: return True\n").unwrap();
    let before = invoke("measure", root, &manifest, &["--require-complete"]);
    assert!(before.status.success());
    let typed = invoke(
        "application-sites",
        root,
        &manifest,
        &["--profile", "python-decisions-v1"],
    );
    let old = invoke("application-sites", root, &manifest, &[]);
    let flow = invoke(
        "application-sites",
        root,
        &manifest,
        &["--profile", "python-decision-flow-v1"],
    );
    assert!(
        flow.status.success(),
        "{}",
        String::from_utf8_lossy(&flow.stderr)
    );
    assert!(flow.stderr.is_empty());
    let flow: Value = serde_json::from_slice(&flow.stdout).unwrap();
    assert_eq!(flow["linked_bindings"], 1);
    assert_eq!(flow["metric_effect"], "none");
    assert_eq!(
        flow["applications"],
        serde_json::from_slice::<Value>(&typed.stdout).unwrap()
    );
    let scan = invoke("scan", root, &manifest, &[]);
    let scan: Value = serde_json::from_slice(&scan.stdout).unwrap();
    assert_eq!(
        flow["bindings"][0]["branch"]["candidate_fingerprint"],
        scan["candidates"][0]["fingerprint"]
    );
    assert_eq!(flow["applications"]["source_digest"], scan["source_digest"]);
    assert_eq!(
        before.stdout,
        invoke("measure", root, &manifest, &["--require-complete"]).stdout
    );
    assert_eq!(
        old.stdout,
        invoke("application-sites", root, &manifest, &[]).stdout
    );
    assert_eq!(
        typed.stdout,
        invoke(
            "application-sites",
            root,
            &manifest,
            &["--profile", "python-decisions-v1"]
        )
        .stdout
    );
}

#[test]
fn typed_profile_is_opt_in_and_does_not_change_default_or_primary_reports() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path();
    let manifest = root.join("scope.toml");
    fs::write(
        &manifest,
        "schema_version = 1\n[[source_sets]]\nrole = 'application'\npaths = ['app.py']\n",
    )
    .unwrap();
    fs::write(root.join("app.py"), "from specification_core import FirstMatch\nRULE = FirstMatch.with_fallback((), 'ready')\nresult = RULE.decide(None).value\nif result: pass\n").unwrap();
    let before = invoke("measure", root, &manifest, &["--require-complete"]);
    assert!(before.status.success());
    let default_before = invoke("application-sites", root, &manifest, &[]);
    let typed = invoke(
        "application-sites",
        root,
        &manifest,
        &["--profile", "python-decisions-v1"],
    );
    assert!(
        typed.status.success(),
        "{}",
        String::from_utf8_lossy(&typed.stderr)
    );
    let typed: Value = serde_json::from_slice(&typed.stdout).unwrap();
    assert_eq!(typed["examined_decide_calls"], 1);
    assert_eq!(typed["direct_application"], 1);
    assert_eq!(typed["metric_effect"], "none");
    assert_eq!(typed["provisional"], false);
    let raw: Value = serde_json::from_slice(&before.stdout).unwrap();
    assert_eq!(typed["source_digest"], raw["source_digest"]);
    assert_eq!(typed["scope_manifest_digest"], raw["scope_manifest_digest"]);
    assert_eq!(raw["remaining_opportunities"], 1);
    assert_eq!(
        before.stdout,
        invoke("measure", root, &manifest, &["--require-complete"]).stdout
    );
    assert_eq!(
        default_before.stdout,
        invoke("application-sites", root, &manifest, &[]).stdout
    );
    assert_eq!(
        default_before.stdout,
        invoke(
            "application-sites",
            root,
            &manifest,
            &["--profile", "python-if-v1"]
        )
        .stdout
    );
}

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
