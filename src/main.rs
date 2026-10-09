mod classify;
mod collection;
mod live;
mod liveness;
mod metric;
mod model;
mod reuse;
mod scan;
mod scope;
mod store;
mod target;

use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};
use clap::{Parser, Subcommand};
use serde::Serialize;

#[derive(Parser)]
#[command(
    version,
    about = "Measure live Specification adoption in Python, Swift, and Rust"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Extract one explicitly selected Python decision expression (experimental).
    ExtractDecisionTarget {
        root: PathBuf,
        #[arg(long)]
        path: String,
        /// 1-based line of the exact syntax-node anchor.
        #[arg(long)]
        line: usize,
        /// 1-based UTF-8 byte column of the exact syntax-node anchor.
        #[arg(long)]
        column: usize,
        #[arg(long)]
        syntax_kind: String,
        #[arg(long, value_enum)]
        select: target::Selection,
        /// Optional blake3:<hex> file digest from a previous snapshot.
        #[arg(long)]
        expected_source_digest: Option<String>,
        #[arg(long)]
        output: Option<PathBuf>,
    },
    /// Detect new Python procedural copies of registered Specification rules.
    CheckRuleReuse {
        root: PathBuf,
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        base: String,
        #[arg(long, default_value = "HEAD")]
        head: String,
        #[arg(long)]
        output: Option<PathBuf>,
        #[arg(long)]
        store: Option<PathBuf>,
        /// Fail on incomplete analysis or newly introduced registered templates.
        #[arg(long)]
        strict: bool,
        /// Ask Jev about new near matches; suggestions never change gate decisions.
        #[arg(long)]
        classify_near_matches: bool,
        #[arg(long)]
        allow_hosted_classification: bool,
        #[arg(long, default_value = "https://api.typesafe.ai/v1/systemone")]
        endpoint: String,
        #[arg(long, default_value = "jev-1.13.0")]
        model: String,
        #[arg(long, default_value = "JEV_API_KEY")]
        api_key_env: String,
        #[arg(long, default_value_t = 30)]
        timeout_seconds: u64,
    },
    /// Generate a committed rule's declaration digest for catalog review.
    FingerprintRule {
        root: PathBuf,
        #[arg(long)]
        path: String,
        #[arg(long)]
        symbol: String,
        #[arg(long, default_value = "HEAD")]
        at: String,
    },
    /// Read rule reuse snapshots separately from primary S/U measurements.
    RuleReuseHistory {
        #[arg(long)]
        store: PathBuf,
        #[arg(long, default_value_t = 20)]
        limit: usize,
    },
    /// Collect primary S/U counters and opt-in external metrics from a TOML contract.
    Collect {
        #[arg(long)]
        config: PathBuf,
        #[arg(long)]
        output: Option<PathBuf>,
        #[arg(long)]
        store: Option<PathBuf>,
        /// Fail unless the primary and all requested supplementary metrics are complete.
        #[arg(long)]
        require_complete: bool,
    },
    /// Compare two collection JSON snapshots under the same measurement contract.
    Compare {
        before: PathBuf,
        after: PathBuf,
        #[arg(long)]
        output: Option<PathBuf>,
    },
    /// Read combined collection snapshots from SQLite, newest first.
    CollectionHistory {
        #[arg(long)]
        store: PathBuf,
        #[arg(long, default_value_t = 20)]
        limit: usize,
    },
    /// Discover Python, Swift, and Rust control-flow candidates.
    Scan {
        root: PathBuf,
        /// Restrict discovery to a relative file or directory (repeatable).
        #[arg(long = "include")]
        includes: Vec<String>,
        /// Classify every discovered source file by its owned source role.
        #[arg(long)]
        scope_manifest: Option<PathBuf>,
        #[arg(long)]
        output: Option<PathBuf>,
    },
    /// Add newly discovered candidates to a durable TOML registry.
    Sync {
        root: PathBuf,
        #[arg(long)]
        registry: PathBuf,
        /// Add a relative file or directory to the registry scope (repeatable).
        #[arg(long = "include")]
        includes: Vec<String>,
        #[arg(long, conflicts_with = "includes")]
        scope_manifest: Option<PathBuf>,
        /// Persist candidates from files with parser errors; reports remain provisional.
        #[arg(long)]
        allow_partial: bool,
    },
    /// Calculate the live Specification definitions / remaining opportunities ratio.
    Measure {
        root: PathBuf,
        /// Apply reviewed exclusions and reuse the registry's source scope.
        #[arg(long)]
        registry: Option<PathBuf>,
        /// Restrict measurement to a relative file or directory (repeatable).
        #[arg(long = "include")]
        includes: Vec<String>,
        #[arg(long, conflicts_with = "includes")]
        scope_manifest: Option<PathBuf>,
        /// Save an idempotent snapshot to a SQLite metric store.
        #[arg(long)]
        store: Option<PathBuf>,
        #[arg(long)]
        output: Option<PathBuf>,
        /// Fail when source files contain parse issues.
        #[arg(long)]
        require_complete: bool,
    },
    /// Report the earlier evidence-coverage metric from a reviewed registry.
    MeasureEvidence {
        root: PathBuf,
        #[arg(long)]
        registry: PathBuf,
        #[arg(long)]
        scope_manifest: Option<PathBuf>,
        #[arg(long)]
        output: Option<PathBuf>,
        #[arg(long)]
        require_complete: bool,
    },
    /// Read saved live metric snapshots, newest first.
    History {
        #[arg(long)]
        store: PathBuf,
        #[arg(long, default_value_t = 20)]
        limit: usize,
    },
    /// Ask Jev to classify scanner candidates as optional, informational suggestions.
    Classify {
        #[arg(long)]
        scan: PathBuf,
        #[arg(long)]
        profile: PathBuf,
        #[arg(long)]
        registry: Option<PathBuf>,
        #[arg(long)]
        scope_manifest: Option<PathBuf>,
        #[arg(long, default_value = "https://api.typesafe.ai/v1/systemone")]
        endpoint: String,
        #[arg(long, default_value = "jev-latest")]
        model: String,
        #[arg(long, default_value = "JEV_API_KEY")]
        api_key_env: String,
        /// Required because candidate source context is sent to a hosted provider.
        #[arg(long)]
        allow_hosted_classification: bool,
        #[arg(long, default_value_t = 30)]
        timeout_seconds: u64,
        /// Jev-specific threshold applied independently to both Choice answers.
        #[arg(long)]
        min_confidence: Option<f64>,
        #[arg(long)]
        output: Option<PathBuf>,
    },
}

#[derive(Serialize)]
struct SyncResult {
    registry: String,
    added: usize,
    registered_sites: usize,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::ExtractDecisionTarget {
            root,
            path,
            line,
            column,
            syntax_kind,
            select,
            expected_source_digest,
            output,
        } => {
            let report = target::extract(
                &root,
                &path,
                line,
                column,
                &syntax_kind,
                select,
                expected_source_digest.as_deref(),
            )?;
            emit_json(&report, output.as_deref())?;
        }
        Command::CheckRuleReuse {
            root,
            catalog,
            base,
            head,
            output,
            store,
            strict,
            classify_near_matches,
            allow_hosted_classification,
            endpoint,
            model,
            api_key_env,
            timeout_seconds,
        } => {
            let client = if classify_near_matches {
                anyhow::ensure!(
                    allow_hosted_classification,
                    "Jev source classification requires --allow-hosted-classification"
                );
                anyhow::ensure!(timeout_seconds > 0, "timeout must be positive");
                let token = std::env::var(&api_key_env)
                    .context("Jev API key environment variable is not configured")?;
                anyhow::ensure!(!token.trim().is_empty(), "Jev API key is empty");
                Some(classify::JevClient::new(
                    &endpoint,
                    &model,
                    token,
                    std::time::Duration::from_secs(timeout_seconds),
                )?)
            } else {
                None
            };
            let report = reuse::check(&root, &catalog, &base, &head, client.as_ref())?;
            emit_json(&report, output.as_deref())?;
            if let Some(store) = store {
                reuse::save(&store, &report)?;
            }
            if strict && (report.status != "complete" || report.new_reimplementations > 0) {
                bail!(
                    "rule reuse gate failed: status={}, new_reimplementations={}",
                    report.status,
                    report.new_reimplementations
                );
            }
        }
        Command::FingerprintRule {
            root,
            path,
            symbol,
            at,
        } => {
            emit_json(&reuse::definition(&root, &at, &path, &symbol)?, None)?;
        }
        Command::RuleReuseHistory { store, limit } => {
            emit_json(&reuse::history(&store, limit)?, None)?;
        }
        Command::Collect {
            config,
            output,
            store,
            require_complete,
        } => {
            let report = collection::collect(&config)?;
            emit_json(&report, output.as_deref())?;
            if require_complete && report.status != "complete" {
                bail!(
                    "collection is {}: inspect primary and supplementary diagnostics",
                    report.status
                );
            }
            if let Some(path) = store {
                let id = collection::save(&path, &report)?;
                eprintln!("stored collection snapshot {id} in {}", path.display());
            }
        }
        Command::Compare {
            before,
            after,
            output,
        } => {
            let report =
                collection::compare(&collection::load(&before)?, &collection::load(&after)?)?;
            emit_json(&report, output.as_deref())?;
        }
        Command::CollectionHistory { store, limit } => {
            emit_json(&collection::history(&store, limit)?, None)?;
        }
        Command::Scan {
            root,
            includes,
            scope_manifest,
            output,
        } => {
            let manifest = scope_manifest
                .as_deref()
                .map(scope::ScopeManifest::load)
                .transpose()?;
            let report = scan::scan_with_scope(&root, &includes, manifest.as_ref())?;
            emit_json(&report, output.as_deref())?;
        }
        Command::Sync {
            root,
            registry,
            includes,
            scope_manifest,
            allow_partial,
        } => {
            let manifest = scope_manifest
                .as_deref()
                .map(scope::ScopeManifest::load)
                .transpose()?;
            let new_registry = !registry.exists();
            let mut current = metric::load_registry(&registry)?;
            if new_registry {
                current.scope_manifest_digest = manifest
                    .as_ref()
                    .map(|manifest| manifest.digest().to_owned());
            }
            if !includes.is_empty() {
                if current.includes.is_empty() && !current.sites.is_empty() {
                    bail!("cannot narrow a registry that already covers the entire root");
                }
                current.includes.extend(includes);
                current.includes = scan::normalize_includes(&current.includes)?;
            }
            let report = scan::scan_with_scope(&root, &current.includes, manifest.as_ref())?;
            let added = metric::sync(&report, &mut current, allow_partial)?;
            metric::save_registry(&registry, &current)?;
            emit_json(
                &SyncResult {
                    registry: registry.display().to_string(),
                    added,
                    registered_sites: current.sites.len(),
                },
                None,
            )?;
        }
        Command::Measure {
            root,
            registry,
            includes,
            scope_manifest,
            store,
            output,
            require_complete,
        } => {
            let manifest = scope_manifest
                .as_deref()
                .map(scope::ScopeManifest::load)
                .transpose()?;
            let current = registry
                .as_ref()
                .map(|path| metric::load_existing_registry(path))
                .transpose()?;
            let includes = if let Some(current) = &current {
                if includes.is_empty() {
                    current.includes.clone()
                } else {
                    let normalized = scan::normalize_includes(&includes)?;
                    if normalized != current.includes {
                        bail!("--include does not match registry scope");
                    }
                    normalized
                }
            } else {
                includes
            };
            let report = scan::scan_with_scope(&root, &includes, manifest.as_ref())?;
            let metrics = live::measure(&report, current.as_ref())?;
            emit_json(&metrics, output.as_deref())?;
            if require_complete && metrics.provisional {
                bail!(
                    "metric is provisional: resolve parse, marker, scope, or Specification liveness issues"
                );
            }
            if let Some(store) = store {
                let id = store::save(&store, &metrics)?;
                eprintln!("stored metric snapshot {id} in {}", store.display());
            }
        }
        Command::MeasureEvidence {
            root,
            registry,
            scope_manifest,
            output,
            require_complete,
        } => {
            let manifest = scope_manifest
                .as_deref()
                .map(scope::ScopeManifest::load)
                .transpose()?;
            let current = metric::load_existing_registry(&registry)?;
            let report = scan::scan_with_scope(&root, &current.includes, manifest.as_ref())?;
            let metrics = metric::measure(&root, &report, &current)?;
            emit_json(&metrics, output.as_deref())?;
            if require_complete && metrics.provisional {
                bail!(
                    "evidence metric is provisional: review new sites and resolve parse or scope issues"
                );
            }
        }
        Command::History { store, limit } => {
            emit_json(&store::history(&store, limit)?, None)?;
        }
        Command::Classify {
            scan,
            profile,
            registry,
            scope_manifest,
            endpoint,
            model,
            api_key_env,
            allow_hosted_classification,
            timeout_seconds,
            min_confidence,
            output,
        } => {
            let report = classify::classify(classify::ClassifyOptions {
                scan_path: &scan,
                profile_path: &profile,
                registry_path: registry.as_deref(),
                manifest_path: scope_manifest.as_deref(),
                endpoint: &endpoint,
                model: &model,
                api_key_env: &api_key_env,
                allow_hosted: allow_hosted_classification,
                timeout_seconds,
                min_confidence,
            })?;
            emit_json(&report, output.as_deref())?;
        }
    }
    Ok(())
}

fn emit_json<T: Serialize>(payload: &T, output: Option<&Path>) -> Result<()> {
    let serialized =
        serde_json::to_string_pretty(payload).context("cannot serialize JSON report")?;
    if let Some(output) = output {
        if let Some(parent) = output.parent().filter(|p| !p.as_os_str().is_empty()) {
            fs::create_dir_all(parent)
                .with_context(|| format!("cannot create {}", parent.display()))?;
        }
        fs::write(output, format!("{serialized}\n"))
            .with_context(|| format!("cannot write {}", output.display()))?;
    } else {
        println!("{serialized}");
    }
    Ok(())
}
