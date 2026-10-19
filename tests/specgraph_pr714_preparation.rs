use std::{path::Path, process::Command};

#[test]
fn historical_pr714_packets_prepare_offline_without_model_execution() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let venv = root.join(".venv/bin/python");
    let python = if venv.exists() {
        venv.as_path()
    } else {
        Path::new("python3")
    };
    for arguments in [
        vec![
            "-m",
            "unittest",
            "-v",
            "test_specgraph_pr714_live_v1.TransportTests",
        ],
        vec![
            "-m",
            "unittest",
            "-v",
            "test_specgraph_pr714_preparation_v1.PreparationTests",
        ],
        vec![
            "prepare_specgraph_pr714_v1.py",
            "verify",
            "--binary",
            env!("CARGO_BIN_EXE_specification-metrics"),
        ],
        vec![
            "-m",
            "unittest",
            "-v",
            "test_specgraph_pr714_preparation_v2.PreparationTests",
        ],
        vec![
            "prepare_specgraph_pr714_v2.py",
            "verify",
            "--binary",
            env!("CARGO_BIN_EXE_specification-metrics"),
        ],
    ] {
        let result = Command::new(python)
            .arg("-B")
            .args(arguments)
            .current_dir(root.join("evals/jev-classification"))
            .output()
            .unwrap();
        assert!(
            result.status.success(),
            "PR714 offline preparation failed:\n{}\n{}",
            String::from_utf8_lossy(&result.stdout),
            String::from_utf8_lossy(&result.stderr)
        );
    }
}
