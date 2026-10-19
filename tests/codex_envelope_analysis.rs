use std::{path::Path, process::Command};

#[test]
fn interrupted_envelope_run_is_diagnosed_without_inference() {
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
            "test_codex_envelope_analysis_v2.py",
        ])
        .current_dir(root.join("evals/jev-classification"))
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "interrupted run analysis failed:\n{}\n{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
}
