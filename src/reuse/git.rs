//! Read committed snapshots. Never checkout, clean, fetch or execute source code.
use std::path::Path;
use std::process::Command;

use anyhow::{Result, ensure};

fn command(root: &Path, args: &[&str]) -> Result<Vec<u8>> {
    let output = Command::new("git")
        .arg("-C")
        .arg(root)
        .args(args)
        .output()?;
    ensure!(
        output.status.success(),
        "Git snapshot operation failed: {}",
        args.first().unwrap_or(&"")
    );
    Ok(output.stdout)
}

pub(super) fn revision(root: &Path, reference: &str) -> Result<String> {
    ensure!(
        !reference.starts_with('-') && !reference.is_empty(),
        "invalid Git reference"
    );
    let expression = format!("{reference}^{{commit}}");
    Ok(
        String::from_utf8(command(root, &["rev-parse", "--verify", &expression])?)?
            .trim()
            .to_owned(),
    )
}

pub(super) fn source(root: &Path, revision: &str, path: &str) -> Result<Option<String>> {
    let object = format!("{revision}:{path}");
    let output = Command::new("git")
        .arg("-C")
        .arg(root)
        .args(["show", &object])
        .output()?;
    if !output.status.success() {
        // Absence is valid only if the exact path is absent from this tree.
        let exists = command(root, &["ls-tree", "-z", revision, "--", path])?;
        ensure!(exists.is_empty(), "cannot read existing Git source: {path}");
        return Ok(None);
    }
    Ok(Some(String::from_utf8(output.stdout)?))
}

#[derive(Debug)]
pub(super) struct ChangedPath {
    pub before: Option<String>,
    pub after: Option<String>,
}

pub(super) fn changed(root: &Path, base: &str, head: &str) -> Result<Vec<ChangedPath>> {
    let bytes = command(
        root,
        &[
            "diff",
            "--name-status",
            "-z",
            "--find-renames",
            base,
            head,
            "--",
        ],
    )?;
    let parts: Vec<_> = bytes.split(|b| *b == 0).filter(|p| !p.is_empty()).collect();
    let mut result = vec![];
    let mut index = 0;
    while index < parts.len() {
        let status = std::str::from_utf8(parts[index])?;
        index += 1;
        let path = String::from_utf8(
            parts
                .get(index)
                .ok_or_else(|| anyhow::anyhow!("malformed Git diff"))?
                .to_vec(),
        )?;
        index += 1;
        let pair = if status.starts_with('R') || status.starts_with('C') {
            let after = String::from_utf8(
                parts
                    .get(index)
                    .ok_or_else(|| anyhow::anyhow!("malformed Git rename"))?
                    .to_vec(),
            )?;
            index += 1;
            ChangedPath {
                before: (!status.starts_with('C')).then_some(path),
                after: Some(after),
            }
        } else {
            ChangedPath {
                before: (status != "A").then_some(path.clone()),
                after: (status != "D").then_some(path),
            }
        };
        result.push(pair);
    }
    Ok(result)
}
