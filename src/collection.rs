//! Reproducible collection: the live S/U report is always the primary metric.
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use anyhow::{Context, Result, ensure};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

use crate::{live, metric, model::LiveMetricReport, scan, scope::ScopeManifest};

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Config {
    pub schema_version: u32,
    /// Stable logical project identity, including across disposable checkouts.
    pub project: String,
    pub root: PathBuf,
    #[serde(default)]
    pub includes: Vec<String>,
    pub scope_manifest: Option<PathBuf>,
    pub registry: Option<PathBuf>,
    #[serde(default)]
    pub supplementary: Supplementary,
}

#[derive(Debug, Default, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Supplementary {
    #[serde(default)]
    pub python_complexity: bool,
    #[serde(default)]
    pub duplication: bool,
    pub python: Option<PathBuf>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct Collection {
    pub schema_version: u32,
    pub project: String,
    pub contract_digest: String,
    pub primary: LiveMetricReport,
    pub supplementary: Value,
    pub status: String,
}

fn resolve(base: &Path, path: &Path) -> PathBuf {
    if path.is_absolute() {
        path.to_owned()
    } else {
        base.join(path)
    }
}

pub fn collect(config_path: &Path) -> Result<Collection> {
    let config_path = config_path.canonicalize()?;
    let base = config_path.parent().context("config has no parent")?;
    let config: Config = toml::from_str(&fs::read_to_string(&config_path)?)?;
    ensure!(
        config.schema_version == 1,
        "unsupported collection config version"
    );
    ensure!(
        !config.project.trim().is_empty(),
        "project must not be empty"
    );
    let root = resolve(base, &config.root);
    let manifest = config
        .scope_manifest
        .as_ref()
        .map(|p| ScopeManifest::load(&resolve(base, p)))
        .transpose()?;
    let registry = config
        .registry
        .as_ref()
        .map(|p| metric::load_existing_registry(&resolve(base, p)))
        .transpose()?;
    let includes = if let Some(registry) = &registry {
        if config.includes.is_empty() {
            registry.includes.clone()
        } else {
            let includes = scan::normalize_includes(&config.includes)?;
            ensure!(
                includes == registry.includes,
                "includes do not match registry scope"
            );
            includes
        }
    } else {
        config.includes.clone()
    };
    let scan = scan::scan_with_scope(&root, &includes, manifest.as_ref())?;
    let primary = live::measure(&scan, registry.as_ref())?;
    // Roots/interpreter locations are execution details, not measurement policy.
    let contract = json!({
        "schema_version": 1,
        "collector_version": env!("CARGO_PKG_VERSION"),
        "adapter_digest": blake3::hash(include_bytes!("../scripts/classic_metrics.py")).to_hex().to_string(),
        "project": config.project,
        "includes": primary.includes,
        "scope_manifest_digest": primary.scope_manifest_digest,
        "registry": registry,
        "counting_rule_version": primary.counting_rule_version,
        "python_complexity": config.supplementary.python_complexity,
        "duplication": config.supplementary.duplication,
    });
    let contract_digest = blake3::hash(&serde_json::to_vec(&contract)?)
        .to_hex()
        .to_string();
    let supplementary = if config.supplementary.python_complexity
        || config.supplementary.duplication
    {
        let workspace = tempfile::tempdir()?;
        let cohort = workspace.path().join("sources");
        fs::create_dir(&cohort)?;
        for source in &scan.sources {
            let path = cohort.join(&source.path);
            fs::create_dir_all(path.parent().context("source has no parent")?)?;
            fs::write(path, &source.bytes)?;
        }
        let script = workspace.path().join("classic_metrics.py");
        fs::write(&script, include_str!("../scripts/classic_metrics.py"))?;
        let python = config
            .supplementary
            .python
            .as_ref()
            .map(|p| {
                if p.components().count() == 1 {
                    p.clone()
                } else {
                    resolve(base, p)
                }
            })
            .unwrap_or_else(|| PathBuf::from("python3"));
        let mut command = Command::new(python);
        command.arg(script).arg(&cohort);
        if config.supplementary.python_complexity {
            command.arg("--complexity");
        }
        if config.supplementary.duplication {
            command.arg("--duplication");
        }
        match command.output() {
            Ok(output) if output.status.success() => {
                serde_json::from_slice::<Value>(&output.stdout).unwrap_or_else(
                    |e| json!({"status":"failed", "error":format!("invalid adapter JSON: {e}")}),
                )
            }
            Ok(output) => {
                json!({"status":"failed", "error":String::from_utf8_lossy(&output.stderr)})
            }
            Err(e) => json!({"status":"failed", "error":e.to_string()}),
        }
    } else {
        json!({"status":"not_requested"})
    };
    let status = if primary.provisional {
        "provisional"
    } else if !matches!(
        supplementary["status"].as_str(),
        Some("complete" | "not_requested")
    ) {
        "partial"
    } else {
        "complete"
    };
    Ok(Collection {
        schema_version: 1,
        project: config.project,
        contract_digest,
        primary,
        supplementary,
        status: status.to_owned(),
    })
}

pub fn compare(before: &Collection, after: &Collection) -> Result<Value> {
    ensure!(
        before.schema_version == 1 && after.schema_version == 1,
        "unsupported collection version"
    );
    ensure!(
        before.project == after.project && before.contract_digest == after.contract_digest,
        "incompatible measurement contracts; compare raw reports separately"
    );
    let b = &before.primary;
    let a = &after.primary;
    let delta = |old: usize, new: usize| new as i128 - old as i128;
    let mut extra = serde_json::Map::new();
    for name in ["python_complexity", "duplication"] {
        let old = &before.supplementary[name];
        let new = &after.supplementary[name];
        if old["status"] == "complete"
            && new["status"] == "complete"
            && old["versions"] == new["versions"]
        {
            let mut values = serde_json::Map::new();
            if let (Some(old), Some(new)) = (old["summary"].as_object(), new["summary"].as_object())
            {
                for (key, value) in old {
                    if let (Some(b), Some(a)) =
                        (value.as_f64(), new.get(key).and_then(Value::as_f64))
                    {
                        values.insert(key.clone(), json!(a - b));
                    }
                }
            }
            extra.insert(
                name.to_owned(),
                json!({"status":"comparable", "delta":values}),
            );
        } else {
            extra.insert(
                name.to_owned(),
                json!({"status":"not_comparable", "delta":null}),
            );
        }
    }
    Ok(json!({
        "schema_version":1, "project":after.project,
        "contract_digest":after.contract_digest,
        "status":if before.status == "complete" && after.status == "complete" {"complete"} else {"provisional"},
        "before_source_digest":b.source_digest, "after_source_digest":a.source_digest,
        "primary":{
            "specification_definitions":{"before":b.specification_definitions,"after":a.specification_definitions,"delta":delta(b.specification_definitions,a.specification_definitions)},
            "remaining_opportunities":{"before":b.remaining_opportunities,"after":a.remaining_opportunities,"delta":delta(b.remaining_opportunities,a.remaining_opportunities)},
            "ratio":{"before":b.ratio,"after":a.ratio,"delta":b.ratio.zip(a.ratio).map(|(b,a)|a-b)},
            "state":{"before":b.state,"after":a.state},
            "dead_specifications_delta":delta(b.dead_specifications,a.dead_specifications),
            "unknown_specifications_delta":delta(b.unknown_specifications,a.unknown_specifications)
        },
        "supplementary":extra,
        "interpretation":"Deltas are observations, not a refactoring quality score or proof of correctness."
    }))
}

pub fn load(path: &Path) -> Result<Collection> {
    serde_json::from_slice(&fs::read(path)?).context("invalid collection snapshot")
}

pub fn save(path: &Path, report: &Collection) -> Result<i64> {
    if let Some(parent) = path.parent().filter(|p| !p.as_os_str().is_empty()) {
        fs::create_dir_all(parent)?;
    }
    let connection = rusqlite::Connection::open(path)?;
    connection.execute_batch("CREATE TABLE IF NOT EXISTS collections (
        id INTEGER PRIMARY KEY, recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        snapshot_key TEXT NOT NULL UNIQUE, report_json TEXT NOT NULL);")?;
    let payload = serde_json::to_string(report)?;
    let key = blake3::hash(payload.as_bytes()).to_hex().to_string();
    connection.execute(
        "INSERT OR IGNORE INTO collections(snapshot_key, report_json) VALUES (?1,?2)",
        rusqlite::params![key, payload],
    )?;
    Ok(connection.query_row(
        "SELECT id FROM collections WHERE snapshot_key=?1",
        [key],
        |r| r.get(0),
    )?)
}

pub fn history(path: &Path, limit: usize) -> Result<Value> {
    ensure!(path.is_file(), "collection store does not exist");
    ensure!(
        (1..=1000).contains(&limit),
        "history limit must be 1..=1000"
    );
    let connection =
        rusqlite::Connection::open_with_flags(path, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY)?;
    let mut statement = connection.prepare(
        "SELECT id, recorded_at, report_json FROM collections ORDER BY id DESC LIMIT ?1",
    )?;
    let rows = statement.query_map([limit as i64], |r| {
        Ok((
            r.get::<_, i64>(0)?,
            r.get::<_, String>(1)?,
            r.get::<_, String>(2)?,
        ))
    })?;
    let mut entries = Vec::new();
    for row in rows {
        let (id, recorded_at, payload) = row?;
        entries.push(json!({"id":id,"recorded_at":recorded_at,"report":serde_json::from_str::<Value>(&payload)?}));
    }
    Ok(json!(entries))
}
