mod metric;
mod model;
mod scan;

use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};
use clap::{Parser, Subcommand};
use serde::Serialize;

#[derive(Parser)]
#[command(
    version,
    about = "Measure reviewed SpecificationCore refactoring opportunities"
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
        /// Persist candidates from files with parser errors; reports remain provisional.
        #[arg(long)]
        allow_partial: bool,
    },
    /// Calculate coverage from reviewed registry entries and current source.
    Measure {
        root: PathBuf,
        #[arg(long)]
        registry: PathBuf,
        #[arg(long)]
        output: Option<PathBuf>,
        #[arg(long)]
        require_complete: bool,
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
            output,
        } => {
            let report = scan::scan(&root, &includes)?;
            emit_json(&report, output.as_deref())?;
        }
        Command::Sync {
            root,
            registry,
            includes,
            allow_partial,
        } => {
            let mut current = metric::load_registry(&registry)?;
            if !includes.is_empty() {
                if current.includes.is_empty() && !current.sites.is_empty() {
                    bail!("cannot narrow a registry that already covers the entire root");
                }
                current.includes.extend(includes);
                current.includes = scan::normalize_includes(&current.includes)?;
            }
            let report = scan::scan(&root, &current.includes)?;
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
            output,
            require_complete,
        } => {
            let current = metric::load_registry(&registry)?;
            let report = scan::scan(&root, &current.includes)?;
            let metrics = metric::measure(&root, &report, &current)?;
            emit_json(&metrics, output.as_deref())?;
            if require_complete && metrics.provisional {
                bail!("metric is provisional: review new sites and resolve parse issues");
            }
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
