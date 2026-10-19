use std::{path::Path, process::Command};

#[test]
fn real_specgraph_packet_preserves_frozen_evidence_and_offline_preparation() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let venv_python = root.join(".venv/bin/python");
    let python = if venv_python.exists() {
        venv_python.as_path()
    } else {
        Path::new("python3")
    };
    let result = Command::new(python)
        .arg("-B")
        .arg(root.join("evals/jev-classification/verify_codex_one_packet_v1.py"))
        .arg("--binary")
        .arg(env!("CARGO_BIN_EXE_specification-metrics"))
        .current_dir(root)
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "offline preparation verification failed:\n{}\n{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
}

#[test]
fn captured_codex_run_keeps_bindings_and_semantic_disagreement_without_inference() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let venv_python = root.join(".venv/bin/python");
    let python = if venv_python.exists() {
        venv_python.as_path()
    } else {
        Path::new("python3")
    };
    let result = Command::new(python)
        .arg("-B")
        .arg(root.join("evals/jev-classification/verify_codex_live_v1.py"))
        .current_dir(root)
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "captured observation verification failed:\n{}\n{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
    // Validate the adapter's BLAKE3 capture bindings using its own hash algorithm
    // without needing any local executable/authentication path from the capture.
    let bundle = root.join("evals/jev-classification/runs/2026-10-19-codex-one-packet-live-v1");
    let report: serde_json::Value =
        serde_json::from_slice(&std::fs::read(bundle.join("report.json")).unwrap()).unwrap();
    for (name, digest) in report["capture_digests"].as_object().unwrap() {
        let actual = format!(
            "blake3:{}",
            blake3::hash(&std::fs::read(bundle.join(name)).unwrap())
        );
        assert_eq!(digest.as_str().unwrap(), actual, "capture changed: {name}");
    }
    let prepared =
        specification_metrics::backend::load_prepared(&bundle.join("prepared.json")).unwrap();
    assert_eq!(
        prepared,
        specification_metrics::backend::prepare(prepared.packet.clone(), prepared.config.clone())
            .unwrap()
    );
}
