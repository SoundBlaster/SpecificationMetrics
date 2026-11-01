//! Snapshot evidence for the remaining-opportunities partition.
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;
use std::process::Command;

use anyhow::{Result, ensure};
use serde::{Deserialize, Serialize};

use crate::collection::Collection;
use crate::model::{Candidate, LiveMetricReport, ScanReport};

const VERSION: u32 = 1;

#[derive(Debug, Serialize, Deserialize)]
pub struct Inventory {
    version: u32,
    repo_prefix: Option<String>,
    verified_paths: BTreeSet<String>,
    sites: Vec<Site>,
}

#[derive(Debug, Serialize, Deserialize)]
struct Site {
    path: String,
    line: usize,
    column: usize,
    kind: String,
    fingerprint: String,
}

pub fn inventory(
    scan: &ScanReport,
    primary: &LiveMetricReport,
    candidates: Vec<&Candidate>,
) -> Inventory {
    let root = Path::new(&scan.root);
    let directory = if root.is_file() {
        root.parent().unwrap_or(root)
    } else {
        root
    };
    let git = |args: &[&str]| {
        Command::new("git")
            .current_dir(directory)
            .args(args)
            .output()
            .ok()
            .filter(|out| out.status.success())
            .map(|out| out.stdout)
    };
    let repo_prefix = git(&["rev-parse", "--show-prefix"])
        .and_then(|v| String::from_utf8(v).ok())
        .and_then(|s| s.strip_suffix('\n').map(str::to_owned));
    let paths: BTreeSet<_> = candidates.iter().map(|c| c.path.as_str()).collect();
    let mut verified_paths = BTreeSet::new();
    if let (Some(prefix), Some(revision)) = (&repo_prefix, &primary.source_revision) {
        for source in &scan.sources {
            if paths.contains(source.path.as_str()) {
                let object = format!("{revision}:{prefix}{}", source.path);
                if git(&["cat-file", "blob", &object]).is_some_and(|blob| blob == source.bytes) {
                    verified_paths.insert(source.path.clone());
                }
            }
        }
    }
    Inventory {
        version: VERSION,
        repo_prefix,
        verified_paths,
        sites: candidates
            .into_iter()
            .map(|c| Site {
                path: c.path.clone(),
                line: c.line,
                column: c.column,
                kind: c.kind.clone(),
                fingerprint: c.fingerprint.clone(),
            })
            .collect(),
    }
}

#[derive(Serialize)]
struct Side<'a> {
    revision: &'a Option<String>,
    source_digest: &'a str,
    scope_manifest_digest: &'a Option<String>,
    remaining: usize,
    repo_prefix: Option<&'a str>,
}

impl<'a> From<&'a Collection> for Side<'a> {
    fn from(c: &'a Collection) -> Self {
        Self {
            revision: &c.primary.source_revision,
            source_digest: &c.primary.source_digest,
            scope_manifest_digest: &c.primary.scope_manifest_digest,
            remaining: c.primary.remaining_opportunities,
            repo_prefix: c
                .opportunity_sites
                .as_ref()
                .and_then(|i| i.repo_prefix.as_deref()),
        }
    }
}

#[derive(Serialize)]
struct Location<'a> {
    #[serde(flatten)]
    site: &'a Site,
    repository_path: Option<String>,
    revision_verified: bool,
}

#[derive(Serialize)]
struct Ambiguous<'a> {
    before: Vec<Location<'a>>,
    after: Vec<Location<'a>>,
}

#[derive(Serialize)]
pub struct Changes<'a> {
    version: u32,
    status: &'static str,
    reason: Option<&'static str>,
    before: Side<'a>,
    after: Side<'a>,
    added: Vec<Location<'a>>,
    removed: Vec<Location<'a>>,
    ambiguous: Vec<Ambiguous<'a>>,
}

fn groups(inventory: &Inventory) -> Result<BTreeMap<&str, Vec<Location<'_>>>> {
    let mut groups: BTreeMap<_, Vec<_>> = BTreeMap::new();
    let mut seen = BTreeSet::new();
    for site in &inventory.sites {
        let Some((key, occurrence)) = site.fingerprint.rsplit_once(':') else {
            anyhow::bail!("invalid candidate fingerprint");
        };
        ensure!(
            occurrence.parse::<usize>().is_ok_and(|n| n > 0)
                && seen.insert(&site.fingerprint)
                && site.line > 0
                && site.column > 0,
            "invalid or duplicate candidate location"
        );
        groups.entry(key).or_default().push(Location {
            site,
            repository_path: inventory
                .repo_prefix
                .as_ref()
                .map(|p| format!("{p}{}", site.path)),
            revision_verified: inventory.verified_paths.contains(&site.path),
        });
    }
    Ok(groups)
}

pub fn compare<'a>(before: &'a Collection, after: &'a Collection) -> Result<Changes<'a>> {
    let mut result = Changes {
        version: VERSION,
        status: "unavailable",
        reason: None,
        before: before.into(),
        after: after.into(),
        added: vec![],
        removed: vec![],
        ambiguous: vec![],
    };
    let (Some(b), Some(a)) = (&before.opportunity_sites, &after.opportunity_sites) else {
        result.reason = Some("missing_inventory");
        return Ok(result);
    };
    if b.version != VERSION || a.version != VERSION {
        result.reason = Some("unsupported_inventory_version");
        return Ok(result);
    }
    if b.repo_prefix.is_some() && a.repo_prefix.is_some() && b.repo_prefix != a.repo_prefix {
        result.reason = Some("different_repository_roots");
        return Ok(result);
    }
    ensure!(
        b.sites.len() == result.before.remaining && a.sites.len() == result.after.remaining,
        "location inventory disagrees with U"
    );
    let mut old = groups(b)?;
    let mut new = groups(a)?;
    let keys: BTreeSet<_> = old.keys().chain(new.keys()).copied().collect();
    for key in keys {
        let b = old.remove(key).unwrap_or_default();
        let a = new.remove(key).unwrap_or_default();
        if b.is_empty() {
            result.added.extend(a);
        } else if a.is_empty() {
            result.removed.extend(b);
        } else if b.len() != a.len() {
            result.ambiguous.push(Ambiguous {
                before: b,
                after: a,
            });
        }
    }
    for rows in [&mut result.added, &mut result.removed] {
        rows.sort_by_key(|row| {
            (
                &row.site.path,
                row.site.line,
                row.site.column,
                &row.site.fingerprint,
            )
        });
    }
    result.status = if before.primary.provisional || after.primary.provisional {
        "provisional"
    } else {
        "complete"
    };
    Ok(result)
}

// Percent-encode source-controlled text before putting it in a Markdown label or URL.
pub(crate) fn encoded(s: &str) -> String {
    let mut out = String::new();
    for b in s.bytes() {
        if b.is_ascii_alphanumeric() || b"-_./".contains(&b) {
            out.push(char::from(b));
        } else {
            use std::fmt::Write;
            write!(out, "%{b:02X}").unwrap();
        }
    }
    out
}

impl Changes<'_> {
    pub fn markdown(&self, repo: &str) -> Result<String> {
        let parts: Vec<_> = repo.split('/').collect();
        ensure!(
            parts.len() == 2
                && parts.iter().all(|s| !s.is_empty()
                    && !matches!(*s, "." | "..")
                    && s.bytes()
                        .all(|b| b.is_ascii_alphanumeric() || b"._-".contains(&b))),
            "expected a GitHub OWNER/REPO"
        );
        let mut lines = vec![format!(
            "### Remaining opportunities (U) · {} → {} ({:+})",
            self.before.remaining,
            self.after.remaining,
            self.after.remaining as i128 - self.before.remaining as i128
        )];
        if let Some(reason) = self.reason {
            lines.push(format!("Locations unavailable (`{reason}`)."));
            return Ok(lines.join("\n\n"));
        }
        let ambiguous_delta: i128 = self
            .ambiguous
            .iter()
            .map(|group| group.after.len() as i128 - group.before.len() as i128)
            .sum();
        lines.push(String::new());
        lines.push(format!(
            "Location comparison **{}**. Added {}, removed {}, ambiguous groups {} (contribution to ΔU: {:+}).",
            self.status,
            self.added.len(),
            self.removed.len(),
            self.ambiguous.len(),
            ambiguous_delta
        ));
        lines.push(format!(
            "Total ΔU: {} − {} + ({:+}) = {:+}.",
            self.added.len(),
            self.removed.len(),
            ambiguous_delta,
            self.after.remaining as i128 - self.before.remaining as i128
        ));
        if self.added.is_empty() && self.removed.is_empty() && self.ambiguous.is_empty() {
            return Ok(lines.join("\n"));
        }
        lines.push(
            "\n<details>\n<summary>Source locations (added, removed and ambiguous)</summary>\n"
                .into(),
        );
        let rows = self
            .added
            .iter()
            .map(|r| ("Added", r, &self.after))
            .chain(self.removed.iter().map(|r| ("Removed", r, &self.before)))
            .chain(self.ambiguous.iter().flat_map(|g| {
                g.before
                    .iter()
                    .map(|r| ("Ambiguous base", r, &self.before))
                    .chain(g.after.iter().map(|r| ("Ambiguous head", r, &self.after)))
            }));
        let mut bytes_left = 12000;
        for (i, (label, row, side)) in rows.enumerate() {
            if i == 20 {
                lines.push("More locations in the JSON comparison.".into());
                break;
            }
            let path = row.repository_path.as_deref().unwrap_or(&row.site.path);
            let location = format!("`{}:{}:{}`", encoded(path), row.site.line, row.site.column);
            let link =
                if let Some(rev) = side.revision.as_ref().filter(|s| {
                    matches!(s.len(), 40 | 64) && s.bytes().all(|b| b.is_ascii_hexdigit())
                }) && row.revision_verified
                    && row.repository_path.is_some()
                    && path.split('/').all(|c| !matches!(c, "" | "." | ".."))
                {
                    format!(
                        "[{location}](https://github.com/{repo}/blob/{rev}/{}#L{})",
                        encoded(path),
                        row.site.line
                    )
                } else {
                    format!("{location} (revision link unavailable)")
                };
            let line = format!("- {label} {link} · `{}`", encoded(&row.site.kind));
            if line.len() + 1 > bytes_left {
                lines.push("More locations in the JSON comparison.".into());
                break;
            }
            bytes_left -= line.len() + 1;
            lines.push(line);
        }
        lines.push("\n</details>".into());
        Ok(lines.join("\n"))
    }
}
