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
