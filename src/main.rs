mod live;
mod liveness;
mod metric;
mod model;
mod scan;
mod scope;
mod store;

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
    /// Discover Python, Swift, and Rust control-flow candidates.
    Scan {
        root: PathBuf,
        /// Restrict discovery to a relative file or directory (repeatable).
        #[arg(long = "include")]
        includes: Vec<String>,
        /// Classify every discovered source file by its owned source role.
        #[arg(long, conflicts_with = "includes")]
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
                    "metric is provisional: resolve source parse, scope, or Specification liveness issues"
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
    }
    Ok(())
}

fn emit_json<T: Serialize>(payload: &T, output: Option<&Path>) -> Result<()> {
    let serialized =
        serde_json::to_string_pretty(payload).context("cannot serialize JSON report")?;
    if let Some(output) = output {
        if let Some(parent) = output.parent() {
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
