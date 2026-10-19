use super::contract::{ADAPTER, BackendConfig, PreparedTask, bounded_file, digest, read_json};
use anyhow::{Result, ensure};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    collections::BTreeMap,
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    path::Path,
    time::{Duration, Instant},
};

#[derive(Debug, Serialize)]
pub struct ExecutionReport {
    pub adapter: &'static str,
    pub status: &'static str,
    pub diagnostic: Option<String>,
    pub packet_digest: String,
    pub config_digest: String,
    pub prompt_digest: String,
    pub answers: Option<BTreeMap<String, String>>,
    pub requested_model: String,
    pub returned_model: Option<String>,
    pub native_probabilities: Option<Value>,
    pub usage: Option<Value>,
    pub monetary_cost: Option<Value>,
    pub inference_process_invocations: usize,
    pub hosted_request_count: Option<usize>,
    pub elapsed_ms: u128,
    pub semantic_validation_status: &'static str,
    pub metric_effect: &'static str,
    pub capture_digests: BTreeMap<String, String>,
}

/// Preparation is entirely offline. Execution requires a distinct explicit
/// authorization and a fresh run directory; failed attempts are never retried.
pub fn execute(
    prepared: &PreparedTask,
    run_dir: &Path,
    allow_inference: bool,
) -> Result<ExecutionReport> {
    prepared.verify()?;
    ensure!(
        allow_inference,
        "execution requires explicit --allow-hosted-classification"
    );
    execute_platform(prepared, run_dir)
}

#[cfg(not(unix))]
fn execute_platform(_: &PreparedTask, _: &Path) -> Result<ExecutionReport> {
    anyhow::bail!("Codex execution requires Unix process-group supervision in v1")
}

pub fn argv(prepared: &PreparedTask) -> Vec<String> {
    config_argv(&prepared.config)
}

pub(super) fn config_argv(config: &BackendConfig) -> Vec<String> {
    let mut args = [
        "exec",
        "--ignore-user-config",
        "--strict-config",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--color",
        "never",
        "--json",
        "--output-schema",
        "response.schema.json",
        "--output-last-message",
        "answer.json",
        "--model",
    ]
    .map(String::from)
    .to_vec();
    args.push(config.model.clone());
    for setting in [
        "approval_policy=\"never\"",
        "model_provider=\"openai\"",
        "project_doc_max_bytes=0",
        "skills.include_instructions=false",
        "web_search=\"disabled\"",
        "mcp_servers={}",
        "features.shell_tool=false",
        "features.view_image=false",
        "features.sleep_tool=false",
        "features.multi_agent=false",
        "features.multi_agent_v2=false",
        "features.apps=false",
        "features.plugins=false",
        "features.hooks=false",
        "features.memories=false",
        "features.code_mode=false",
        "features.browser_use=false",
        "features.computer_use=false",
        "features.image_generation=false",
        "features.standalone_web_search=false",
        "features.skill_search=false",
        "features.goals=false",
    ] {
        args.extend(["-c".into(), setting.into()]);
    }
    let effort = serde_json::to_string(&config.reasoning_effort).unwrap();
    args.extend([
        "-c".into(),
        format!("model_reasoning_effort={effort}"),
        "-".into(),
    ]);
    args
}

#[cfg(unix)]
fn execute_platform(prepared: &PreparedTask, run_dir: &Path) -> Result<ExecutionReport> {
    use super::process::{ProcessLimits, capture};
    use std::os::unix::fs::{DirBuilderExt, OpenOptionsExt};
    ensure!(
        run_dir.is_absolute() && !run_dir.exists(),
        "run directory must be a fresh absolute path"
    );
    let parent = run_dir
        .parent()
        .ok_or_else(|| anyhow::anyhow!("run directory needs a parent"))?
        .canonicalize()?;
    for ancestor in parent.ancestors() {
        ensure!(
            !ancestor.join(".git").exists() && !ancestor.join(".codex/config.toml").exists(),
            "run directory must be outside repository and project configuration ancestry"
        );
    }
    let executable = prepared.config.executable.canonicalize()?;
    let authentication_home = prepared.config.authentication_home.canonicalize()?;
    ensure!(
        authentication_home.is_dir(),
        "authentication_home is not a directory"
    );
    // Global home instructions are loaded independently of project_doc_max_bytes
    // and --ignore-user-config. Never silently add them to a frozen packet.
    for name in ["AGENTS.md", "AGENTS.override.md"] {
        match fs::symlink_metadata(authentication_home.join(name)) {
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(error) => return Err(error.into()),
            Ok(_) => anyhow::bail!(
                "authentication_home contains global instructions; select a dedicated Codex authentication home"
            ),
        }
    }
    let executable_digest = file_digest(&executable)?;
    let adapter_executable = std::env::current_exe()?.canonicalize()?;
    let adapter_executable_digest = file_digest(&adapter_executable)?;
    let version = capture(
        &executable,
        &["--version".into()],
        b"",
        &parent,
        ProcessLimits {
            timeout: Duration::from_secs(5),
            bytes: 4096,
            authentication_home: &authentication_home,
        },
        None,
    )?;
    ensure!(
        version.diagnostic.is_none()
            && std::str::from_utf8(&version.stdout)?.trim() == prepared.config.required_cli_version,
        "CLI version preflight failed; no inference dispatched"
    );
    let args = argv(prepared);
    let runtime = serde_json::to_vec_pretty(&json!({
        "cli_version":prepared.config.required_cli_version,"executable":executable,
        "executable_digest":executable_digest,
        "adapter_executable":adapter_executable,
        "adapter_executable_digest":adapter_executable_digest,
        "os":std::env::consts::OS,"architecture":std::env::consts::ARCH,
        "capability_status":"version_checked_configuration_requested",
        "remote_execution_attested":false
    }))?;
    // Initialize all fallible runtime metadata before reserving a run ID.
    let files = [
        ("prepared.json", serde_json::to_vec_pretty(prepared)?),
        ("argv.json", serde_json::to_vec_pretty(&args)?),
        ("runtime.json", runtime),
        ("request.stdin", prepared.prompt.as_bytes().to_vec()),
        (
            "response.schema.json",
            serde_json::to_vec_pretty(&prepared.response_schema)?,
        ),
    ];
    fs::DirBuilder::new().mode(0o700).create(run_dir)?;
    let mut report = ExecutionReport {
        adapter: ADAPTER,
        status: "analysis_incomplete",
        diagnostic: None,
        packet_digest: prepared.packet_digest.clone(),
        config_digest: prepared.config_digest.clone(),
        prompt_digest: prepared.prompt_digest.clone(),
        answers: None,
        requested_model: prepared.config.model.clone(),
        returned_model: None,
        native_probabilities: None,
        usage: None,
        monetary_cost: None,
        inference_process_invocations: 0,
        hosted_request_count: None,
        elapsed_ms: 0,
        semantic_validation_status: "not_run",
        metric_effect: "none",
        capture_digests: BTreeMap::new(),
    };
    // The new directory is an exclusive durable single-use reservation. Even a
    // successful process cannot reuse the same run ID for a second invocation.
    let started = Instant::now();
    let outcome = (|| -> Result<()> {
        for (name, bytes) in &files {
            save(run_dir, name, bytes, &mut report)?;
        }
        File::open(run_dir)?.sync_all()?;
        let result = capture(
            &executable,
            &args,
            prepared.prompt.as_bytes(),
            run_dir,
            ProcessLimits {
                timeout: Duration::from_secs(prepared.config.timeout_seconds),
                bytes: prepared.config.max_output_bytes,
                authentication_home: &authentication_home,
            },
            Some(&run_dir.join("answer.json")),
        )?;
        report.inference_process_invocations = 1;
        save(run_dir, "events.jsonl", &result.stdout, &mut report)?;
        save(run_dir, "stderr.txt", &result.stderr, &mut report)?;
        if let Some(diagnostic) = result.diagnostic {
            report.diagnostic = Some(diagnostic.into());
            return Ok(());
        }
        let answer_path = run_dir.join("answer.json");
        let metadata = fs::symlink_metadata(&answer_path)?;
        ensure!(
            metadata.file_type().is_file(),
            "final answer is not a regular file"
        );
        // Child processes are reaped before opening the final message.
        let mut final_file = OpenOptions::new()
            .read(true)
            .custom_flags(libc::O_NOFOLLOW)
            .open(&answer_path)?;
        let mut answer = Vec::new();
        std::io::Read::by_ref(&mut final_file)
            .take(prepared.config.max_output_bytes as u64 + 1)
            .read_to_end(&mut answer)?;
        ensure!(
            answer.len() <= prepared.config.max_output_bytes,
            "final answer exceeds limit"
        );
        report
            .capture_digests
            .insert("answer.json".into(), digest(&answer));
        let decoded = validate_output(prepared, &answer, &result.stdout)?;
        report.answers = Some(decoded.0);
        report.usage = decoded.1;
        report.status = "proposal";
        Ok(())
    })();
    if outcome.is_err() && report.diagnostic.is_none() {
        report.diagnostic = Some("invalid_or_unavailable_capture".into());
    }
    report.elapsed_ms = started.elapsed().as_millis();
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(run_dir.join("report.json"))?;
    file.write_all(&serde_json::to_vec_pretty(&report)?)?;
    file.sync_all()?;
    File::open(run_dir)?.sync_all()?;
    Ok(report)
}

#[cfg(unix)]
fn save(dir: &Path, name: &str, bytes: &[u8], report: &mut ExecutionReport) -> Result<()> {
    use std::os::unix::fs::OpenOptionsExt;
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(dir.join(name))?;
    file.write_all(bytes)?;
    file.sync_all()?;
    report.capture_digests.insert(name.into(), digest(bytes));
    Ok(())
}

#[cfg(unix)]
fn file_digest(path: &Path) -> Result<String> {
    let mut hasher = blake3::Hasher::new();
    let mut file = File::open(path)?;
    let mut buffer = [0; 65536];
    loop {
        let n = file.read(&mut buffer)?;
        if n == 0 {
            break;
        }
        hasher.update(&buffer[..n]);
    }
    Ok(format!("blake3:{}", hasher.finalize()))
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Answers {
    answers: BTreeMap<String, String>,
}

fn validate_output(
    prepared: &PreparedTask,
    answer: &[u8],
    events: &[u8],
) -> Result<(BTreeMap<String, String>, Option<Value>)> {
    let decoded: Answers = read_json(answer)?;
    ensure!(
        decoded.answers.len() == prepared.packet.task.questions.len(),
        "missing or extra answers"
    );
    for (id, question) in &prepared.packet.task.questions {
        ensure!(
            decoded
                .answers
                .get(id)
                .is_some_and(|label| question.criteria.contains_key(label)),
            "invalid answer label"
        );
    }
    #[derive(PartialEq)]
    enum Phase {
        Start,
        Thread,
        Turn,
        Complete,
    }
    let mut phase = Phase::Start;
    let mut last_message = None;
    let mut usage = None;
    for line in std::str::from_utf8(events)?
        .lines()
        .filter(|line| !line.trim().is_empty())
    {
        let event: Value = read_json(line.as_bytes())?;
        match (&phase, event["type"].as_str()) {
            (Phase::Start, Some("thread.started")) => phase = Phase::Thread,
            (Phase::Thread, Some("turn.started")) => phase = Phase::Turn,
            (Phase::Turn, Some("item.started" | "item.updated" | "item.completed")) => {
                ensure!(
                    matches!(
                        event["item"]["type"].as_str(),
                        Some("agent_message" | "reasoning")
                    ),
                    "tool activity is not allowed"
                );
                if event["type"] == "item.completed" && event["item"]["type"] == "agent_message" {
                    last_message = event["item"]["text"].as_str().map(str::to_owned);
                }
            }
            (Phase::Turn, Some("turn.completed")) => {
                phase = Phase::Complete;
                if let Some(value) = event.get("usage").filter(|v| !v.is_null()) {
                    ensure!(
                        value.is_object()
                            && ["input_tokens", "output_tokens"]
                                .iter()
                                .all(|key| value[*key].as_u64().is_some()),
                        "invalid usage metadata"
                    );
                    usage = Some(value.clone());
                }
            }
            _ => anyhow::bail!("incomplete, failed or unsupported event stream"),
        }
    }
    ensure!(phase == Phase::Complete, "one completed turn required");
    let message: Value = read_json(
        last_message
            .ok_or_else(|| anyhow::anyhow!("missing final message"))?
            .as_bytes(),
    )?;
    ensure!(
        message == read_json::<Value>(answer)?,
        "event and final-message file disagree"
    );
    Ok((decoded.answers, usage))
}

/// Bounded JSON loading for the CLI, including prepared artifacts.
pub fn load_prepared(path: &Path) -> Result<PreparedTask> {
    read_json(&bounded_file(path, 4 * super::contract::INPUT_LIMIT)?)
}
