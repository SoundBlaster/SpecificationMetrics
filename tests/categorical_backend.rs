use serde_json::{Value, json};
use specification_metrics::backend::{self, Backend, BackendConfig, CategoricalPacket, Effort};
use std::{collections::BTreeMap, fs, path::Path, process::Command, time::Instant};

fn packet() -> CategoricalPacket {
    backend::read_json(&serde_json::to_vec(&json!({
        "schema_version":1,"source_revision":"1111111111111111111111111111111111111111","rubric_version":"test-v1",
        "semantic_instructions":"Prefer named, reusable Specifications for product policy; do not reimplement formatter or linter rules. Use unknown if required evidence is missing.",
        "task":{"state":{"code":"return workspace == approved_workspace","architecture_goal":"Centralize product policy in Specifications."},
        "questions":{"role":{"instructions":"Classify the decision's responsibility.","criteria":{"policy":"Product policy decision.","mechanics":"Transport, syntax or local implementation detail.","unknown":"Insufficient evidence."}}}}
    })).unwrap()).unwrap()
}

fn config(executable: &Path) -> BackendConfig {
    BackendConfig {
        schema_version: 1,
        backend: Backend::CodexCli,
        executable: executable.into(),
        authentication_home: executable.parent().unwrap().into(),
        required_cli_version: "codex-cli 0.156.1".into(),
        model: "configured-test-model".into(),
        reasoning_effort: Effort::Medium,
        timeout_seconds: 1,
        max_output_bytes: 8192,
        require_native_distribution: false,
        max_output_tokens: None,
    }
}

#[test]
fn shared_packet_preserves_semantics_and_does_not_require_an_installed_backend() {
    let packet = packet();
    let prepared =
        backend::prepare(packet.clone(), config(Path::new("/not-installed/codex"))).unwrap();
    assert_eq!(prepared.packet, packet);
    let rendered: Value = serde_json::from_str(prepared.prompt.lines().nth(1).unwrap()).unwrap();
    assert_eq!(rendered, serde_json::to_value(&packet).unwrap());
    assert_eq!(
        prepared.response_schema["properties"]["answers"]["required"],
        json!(["role"])
    );
    let args = backend::codex_argv(&prepared);
    assert_eq!(prepared.arguments, args);
    for required in [
        "--ignore-user-config",
        "--strict-config",
        "--ephemeral",
        "project_doc_max_bytes=0",
        "features.shell_tool=false",
        "features.memories=false",
        "model_reasoning_effort=\"medium\"",
    ] {
        assert!(args.iter().any(|a| a == required), "missing {required}");
    }
    assert_eq!(args.last().unwrap(), "-");
    assert!(
        !args
            .iter()
            .any(|a| a == "resume" || a == "--yolo" || a == "--add-dir")
    );
    assert_eq!(
        prepared.capability_status,
        "configured_not_runtime_verified"
    );
}

#[test]
fn cli_profile_features_are_canonical_active_keys_in_the_pinned_registry() {
    // Independent upstream capability evidence, not a duplicate of our argv.
    let registry: Value = serde_json::from_str(include_str!(
        "fixtures/backends/codex-0.156.1-features.json"
    ))
    .unwrap();
    let prepared = backend::prepare(packet(), config(Path::new("/not-installed/codex"))).unwrap();
    assert_eq!(
        prepared.config.required_cli_version,
        registry["cli_version"]
    );
    let args = backend::codex_argv(&prepared);
    for key in args
        .iter()
        .filter_map(|arg| arg.strip_prefix("features."))
        .map(|arg| arg.split('=').next().unwrap())
    {
        assert!(
            registry["canonical_features"]
                .as_array()
                .unwrap()
                .contains(&json!(key)),
            "noncanonical feature {key}"
        );
        assert!(
            !registry["legacy_aliases"]
                .as_array()
                .unwrap()
                .contains(&json!(key)),
            "legacy feature alias {key}"
        );
        assert!(
            !registry["removed_or_deprecated_features"]
                .as_array()
                .unwrap()
                .contains(&json!(key)),
            "ineffective feature toggle {key}"
        );
    }
}

#[test]
fn cli_profile_disables_default_local_tools_before_dispatch() {
    let registry: Value = serde_json::from_str(include_str!(
        "fixtures/backends/codex-0.156.1-features.json"
    ))
    .unwrap();
    let prepared = backend::prepare(packet(), config(Path::new("/not-installed/codex"))).unwrap();
    let args = backend::codex_argv(&prepared);
    for feature in registry["default_enabled_local_tools_to_disable"]
        .as_array()
        .unwrap()
    {
        let toggle = format!("features.{}=false", feature.as_str().unwrap());
        assert!(
            args.contains(&toggle),
            "default local tool remains enabled: {toggle}"
        );
    }
}

#[test]
fn unsupported_capabilities_and_backends_never_fall_back_or_ignore_settings() {
    let cfg = config(Path::new("/unused"));
    for backend in [
        Backend::SystemOne,
        Backend::GeneralApi,
        Backend::Ollama,
        Backend::LmStudio,
    ] {
        let mut changed = cfg.clone();
        changed.backend = backend;
        assert!(backend::prepare(packet(), changed).is_err());
    }
    let mut changed = cfg.clone();
    changed.require_native_distribution = true;
    assert!(backend::prepare(packet(), changed).is_err());
    let mut changed = cfg.clone();
    changed.max_output_tokens = Some(100);
    assert!(backend::prepare(packet(), changed).is_err());
    let mut changed = cfg.clone();
    changed.required_cli_version = "codex-cli future".into();
    assert!(backend::prepare(packet(), changed).is_err());
    let mut changed = cfg;
    changed.timeout_seconds = 0;
    assert!(backend::prepare(packet(), changed).is_err());
    let mut oversized = packet();
    oversized.semantic_instructions = "x".repeat(65537);
    assert!(backend::prepare(oversized, config(Path::new("/unused"))).is_err());
}

#[test]
fn duplicate_keys_extra_fields_and_wrong_primitives_are_rejected() {
    for bytes in [
        br#"{"answers":{"role":"policy","role":"mechanics"}}"#.as_slice(),
        br#"{"state":{"nested":{"x":1,"x":2}}}"#,
        br#"{"state":1,"state":2}"#,
        br#"{"answers":{}} trailing"#,
    ] {
        assert!(backend::read_json::<Value>(bytes).is_err());
    }
    let mut value = serde_json::to_value(packet()).unwrap();
    value["prior_labels"] = json!({"role":"policy"});
    assert!(backend::read_json::<CategoricalPacket>(&serde_json::to_vec(&value).unwrap()).is_err());
    value.as_object_mut().unwrap().remove("prior_labels");
    value["task"]["questions"]["role"]["type"] = json!("score");
    assert!(backend::read_json::<CategoricalPacket>(&serde_json::to_vec(&value).unwrap()).is_err());
}

#[cfg(unix)]
mod unix {
    use super::*;
    use std::os::unix::fs::PermissionsExt;

    fn fake(root: &Path, body: &str, version: &str) -> std::path::PathBuf {
        let executable = root.join("fake-codex");
        fs::write(&executable, format!("#!/bin/sh\nif [ \"$1\" = --version ]; then printf '%s\\n' '{version}'; exit 0; fi\ncat > received.stdin\nprintf '%s\\n' \"$@\" > received.argv\n{body}\n")).unwrap();
        fs::set_permissions(&executable, fs::Permissions::from_mode(0o700)).unwrap();
        executable
    }

    fn success(answer: Value, final_text: Value, extra: &str) -> String {
        let event = json!({"type":"item.completed","item":{"id":"i","type":"agent_message","text":final_text.to_string()}});
        format!(
            "cat > answer.json <<'ANSWER'\n{answer}\nANSWER\ncat <<'EVENTS'\n{{\"type\":\"thread.started\",\"thread_id\":\"fixture\"}}\n{{\"type\":\"turn.started\"}}\n{event}\n{extra}\n{{\"type\":\"turn.completed\",\"usage\":{{\"input_tokens\":8,\"output_tokens\":4}}}}\nEVENTS"
        )
    }

    #[test]
    fn fake_process_success_retains_proposal_and_provenance_without_inventing_evidence() {
        let root = tempfile::tempdir().unwrap();
        let answer = json!({"answers":{"role":"policy"}});
        let executable = fake(
            root.path(),
            &success(answer.clone(), answer, ""),
            "codex-cli 0.156.1",
        );
        let prepared = backend::prepare(packet(), config(&executable)).unwrap();
        let run = root.path().join("run");
        let report = backend::execute(&prepared, &run, true).unwrap();
        assert_eq!(report.status, "proposal");
        assert_eq!(
            report.answers,
            Some(BTreeMap::from([("role".into(), "policy".into())]))
        );
        assert_eq!(report.semantic_validation_status, "not_run");
        assert_eq!(report.metric_effect, "none");
        assert_eq!(report.usage.unwrap()["input_tokens"], 8);
        assert!(
            report.native_probabilities.is_none()
                && report.monetary_cost.is_none()
                && report.returned_model.is_none()
                && report.hosted_request_count.is_none()
        );
        assert_eq!(report.inference_process_invocations, 1);
        assert_eq!(
            fs::read_to_string(run.join("received.stdin")).unwrap(),
            prepared.prompt
        );
        assert_eq!(
            fs::read_to_string(run.join("received.argv"))
                .unwrap()
                .lines()
                .collect::<Vec<_>>(),
            backend::codex_argv(&prepared)
        );
        assert_eq!(
            fs::metadata(&run).unwrap().permissions().mode() & 0o777,
            0o700
        );
        assert_eq!(
            fs::metadata(run.join("runtime.json"))
                .unwrap()
                .permissions()
                .mode()
                & 0o777,
            0o600
        );
        assert!(report.capture_digests.contains_key("answer.json"));
        assert!(backend::execute(&prepared, &run, true).is_err());
    }

    #[test]
    fn authorization_binding_and_version_fail_before_reservation() {
        let root = tempfile::tempdir().unwrap();
        let executable = fake(root.path(), "exit 99", "codex-cli wrong");
        let mut prepared = backend::prepare(packet(), config(&executable)).unwrap();
        let run = root.path().join("run");
        assert!(backend::execute(&prepared, &run, false).is_err());
        assert!(!run.exists());
        prepared.prompt.push_str(" changed");
        assert!(backend::execute(&prepared, &run, true).is_err());
        assert!(!run.exists());
        prepared = backend::prepare(packet(), config(&executable)).unwrap();
        assert!(backend::execute(&prepared, &run, true).is_err());
        assert!(!run.exists());
        // Correct the preflight defect: the unreserved run path remains usable.
        let answer = json!({"answers":{"role":"unknown"}});
        fake(
            root.path(),
            &success(answer.clone(), answer, ""),
            "codex-cli 0.156.1",
        );
        assert_eq!(
            backend::execute(&prepared, &run, true).unwrap().status,
            "proposal"
        );
    }

    #[test]
    fn invalid_captures_never_turn_into_unknown_or_success() {
        for (answer, final_text, extra) in [
            (
                json!({"answers":{"role":"invented"}}),
                json!({"answers":{"role":"invented"}}),
                "",
            ),
            (json!({"answers":{}}), json!({"answers":{}}), ""),
            (
                json!({"answers":{"role":"policy"},"accepted":true}),
                json!({"answers":{"role":"policy"},"accepted":true}),
                "",
            ),
            (
                json!({"answers":{"role":"policy"}}),
                json!({"answers":{"role":"mechanics"}}),
                "",
            ),
            (
                json!({"answers":{"role":"policy"}}),
                json!({"answers":{"role":"policy"}}),
                "{\"type\":\"turn.failed\",\"error\":\"refused\"}",
            ),
            (
                json!({"answers":{"role":"policy"}}),
                json!({"answers":{"role":"policy"}}),
                "{\"type\":\"item.completed\",\"item\":{\"type\":\"command_execution\"}}",
            ),
        ] {
            let root = tempfile::tempdir().unwrap();
            let executable = fake(
                root.path(),
                &success(answer, final_text, extra),
                "codex-cli 0.156.1",
            );
            let prepared = backend::prepare(packet(), config(&executable)).unwrap();
            let run = root.path().join("run");
            let report = backend::execute(&prepared, &run, true).unwrap();
            assert_eq!(report.status, "analysis_incomplete");
            assert!(report.answers.is_none());
            assert!(run.join("report.json").exists());
            assert!(run.join("events.jsonl").exists());
        }
    }

    #[test]
    fn timeout_overflow_and_nonzero_exit_keep_failed_run_and_do_not_retry() {
        for (body, expected) in [
            ("sleep 30", "timeout"),
            ("head -c 20000 /dev/zero", "output_limit"),
            ("printf 'captured diagnostic' >&2; exit 3", "process_failed"),
        ] {
            let root = tempfile::tempdir().unwrap();
            let executable = fake(root.path(), body, "codex-cli 0.156.1");
            let prepared = backend::prepare(packet(), config(&executable)).unwrap();
            let run = root.path().join("run");
            let started = Instant::now();
            let report = backend::execute(&prepared, &run, true).unwrap();
            assert_eq!(report.status, "analysis_incomplete");
            assert_eq!(report.diagnostic.as_deref(), Some(expected));
            assert!(report.answers.is_none());
            assert_eq!(report.inference_process_invocations, 1);
            assert!(started.elapsed().as_secs() < 5);
            assert!(backend::execute(&prepared, &run, true).is_err());
        }
    }

    #[test]
    fn descendants_holding_pipes_are_reaped_after_parent_exit() {
        let root = tempfile::tempdir().unwrap();
        let executable = fake(root.path(), "sleep 30 &\nexit 4", "codex-cli 0.156.1");
        let prepared = backend::prepare(packet(), config(&executable)).unwrap();
        let started = Instant::now();
        let report = backend::execute(&prepared, &root.path().join("run"), true).unwrap();
        assert_eq!(report.diagnostic.as_deref(), Some("process_failed"));
        assert!(started.elapsed().as_secs() < 5);
    }

    #[test]
    fn run_directory_cannot_inherit_a_repository_configuration() {
        let root = tempfile::tempdir().unwrap();
        fs::create_dir(root.path().join(".git")).unwrap();
        let executable = fake(root.path(), "exit 99", "codex-cli 0.156.1");
        let prepared = backend::prepare(packet(), config(&executable)).unwrap();
        let run = root.path().join("run");
        assert!(backend::execute(&prepared, &run, true).is_err());
        assert!(!run.exists());
    }

    #[test]
    fn global_home_instructions_are_rejected_even_when_user_config_is_ignored() {
        for name in ["AGENTS.md", "AGENTS.override.md"] {
            let root = tempfile::tempdir().unwrap();
            fs::write(
                root.path().join(name),
                "Prior context and labels must not enter the packet",
            )
            .unwrap();
            let executable = fake(root.path(), "exit 99", "codex-cli 0.156.1");
            let prepared = backend::prepare(packet(), config(&executable)).unwrap();
            let run = root.path().join("run");
            let error = backend::execute(&prepared, &run, true).unwrap_err();
            assert!(error.to_string().contains("global instructions"));
            assert!(!run.exists());
        }
    }

    #[test]
    fn incomplete_lifecycle_and_nonregular_final_answers_cannot_be_proposals() {
        let answer = json!({"answers":{"role":"policy"}});
        let good = success(answer.clone(), answer, "");
        let terminal =
            "{\"type\":\"turn.completed\",\"usage\":{\"input_tokens\":8,\"output_tokens\":4}}\n";
        for body in [
            good.replace(terminal, ""),
            format!("{good}\nprintf '%s\\n' '{{\"type\":\"turn.started\"}}'"),
            format!("{good}\nrm answer.json; mkfifo answer.json"),
            format!("{good}\nrm answer.json; ln -s received.stdin answer.json"),
        ] {
            let root = tempfile::tempdir().unwrap();
            let executable = fake(root.path(), &body, "codex-cli 0.156.1");
            let prepared = backend::prepare(packet(), config(&executable)).unwrap();
            let started = Instant::now();
            let report = backend::execute(&prepared, &root.path().join("run"), true).unwrap();
            assert_eq!(report.status, "analysis_incomplete");
            assert!(report.answers.is_none());
            assert!(started.elapsed().as_secs() < 5);
        }
    }

    #[test]
    fn changing_frozen_tool_restrictions_is_rejected_before_reservation() {
        let root = tempfile::tempdir().unwrap();
        let executable = fake(root.path(), "exit 99", "codex-cli 0.156.1");
        let mut prepared = backend::prepare(packet(), config(&executable)).unwrap();
        prepared
            .arguments
            .retain(|arg| arg != "features.view_image=false");
        // Even rebinding the local digest cannot replace the current profile.
        prepared.arguments_digest = format!(
            "blake3:{}",
            blake3::hash(&serde_json::to_vec(&prepared.arguments).unwrap())
        );
        let run = root.path().join("run");
        assert!(
            backend::execute(&prepared, &run, true)
                .unwrap_err()
                .to_string()
                .contains("prepared task binding changed")
        );
        assert!(!run.exists());
    }

    #[test]
    fn configuration_warning_before_turn_is_not_ignored() {
        let root = tempfile::tempdir().unwrap();
        let answer = json!({"answers":{"role":"policy"}});
        let body=success(answer.clone(),answer,"").replace(
            "{\"type\":\"turn.started\"}",
            "{\"type\":\"item.completed\",\"item\":{\"id\":\"warning\",\"type\":\"error\",\"message\":\"legacy feature configuration\"}}\n{\"type\":\"turn.started\"}"
        );
        let executable = fake(root.path(), &body, "codex-cli 0.156.1");
        let prepared = backend::prepare(packet(), config(&executable)).unwrap();
        let report = backend::execute(&prepared, &root.path().join("run"), true).unwrap();
        assert_eq!(report.status, "analysis_incomplete");
        assert!(report.answers.is_none());
    }
}

#[test]
fn cli_preparation_is_offline_and_execution_requires_a_separate_opt_in() {
    let root = tempfile::tempdir().unwrap();
    let packet_path = root.path().join("packet.json");
    let config_path = root.path().join("backend.toml");
    fs::write(&packet_path, serde_json::to_vec(&packet()).unwrap()).unwrap();
    fs::write(
        &config_path,
        toml::to_string(&config(Path::new("/not-installed/codex"))).unwrap(),
    )
    .unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_specification-metrics"))
        .args(["prepare-classification", "--packet"])
        .arg(&packet_path)
        .arg("--config")
        .arg(&config_path)
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let prepared_path = root.path().join("prepared.json");
    fs::write(&prepared_path, &output.stdout).unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_specification-metrics"))
        .args(["run-classification", "--prepared"])
        .arg(&prepared_path)
        .arg("--run-dir")
        .arg(root.path().join("run"))
        .output()
        .unwrap();
    assert!(!output.status.success());
    assert!(!root.path().join("run").exists());
    assert!(
        String::from_utf8_lossy(&output.stderr).contains("explicit --allow-hosted-classification")
    );
}
