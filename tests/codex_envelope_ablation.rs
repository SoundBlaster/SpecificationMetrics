use std::{path::Path, process::Command};

#[test]
fn public_codex_envelope_study_is_replayed_without_inference() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let venv_python = root.join(".venv/bin/python");
    let python = if venv_python.exists() {
        venv_python.as_path()
    } else {
        Path::new("python3")
    };
    let result = Command::new(python)
        .args([
            "-B",
            "-m",
            "unittest",
            "-v",
            "test_codex_envelope_ablation_v1.py",
        ])
        .current_dir(root.join("evals/jev-classification"))
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "offline ablation tests failed:\n{}\n{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
}
