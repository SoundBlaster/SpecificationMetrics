use std::collections::HashSet;
use std::fs;
use std::path::Path;

use anyhow::{Context, Result, bail, ensure};

use crate::model::{Disposition, MetricReport, Registry, SCHEMA_VERSION, ScanReport, Site};

pub fn load_registry(path: &Path) -> Result<Registry> {
    if !path.exists() {
        return Ok(Registry::default());
    }
    let source = fs::read_to_string(path)
        .with_context(|| format!("cannot read registry {}", path.display()))?;
    toml::from_str(&source).with_context(|| format!("invalid registry {}", path.display()))
}

pub fn save_registry(path: &Path, registry: &Registry) -> Result<()> {
    let source = toml::to_string_pretty(registry).context("cannot serialize registry")?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("cannot create {}", parent.display()))?;
    }
    fs::write(path, source).with_context(|| format!("cannot write {}", path.display()))
}

pub fn sync(scan: &ScanReport, registry: &mut Registry, allow_partial: bool) -> Result<usize> {
    ensure!(
        allow_partial || scan.parse_issues.is_empty(),
        "cannot sync a partial scan: {} parse issue(s)",
        scan.parse_issues.len()
    );
    ensure!(
        registry.schema_version == SCHEMA_VERSION,
        "unsupported registry schema version {}",
        registry.schema_version
    );
    ensure!(
        registry.includes == scan.includes,
        "scan scope does not match registry includes"
    );
    let mut known: HashSet<String> = registry
        .sites
        .iter()
        .map(|site| site.fingerprint.clone())
        .collect();
    let mut added = 0;
    for candidate in &scan.candidates {
        if known.insert(candidate.fingerprint.clone()) {
            registry.sites.push(Site::unreviewed(candidate));
            added += 1;
        }
    }
    Ok(added)
}

pub fn measure(root: &Path, scan: &ScanReport, registry: &Registry) -> Result<MetricReport> {
    validate(root, registry)?;
    ensure!(
        registry.includes == scan.includes,
        "scan scope does not match registry includes"
    );
    let registered: HashSet<&str> = registry
        .sites
        .iter()
        .map(|site| site.fingerprint.as_str())
        .collect();
    let current: HashSet<&str> = scan
        .candidates
        .iter()
        .map(|candidate| candidate.fingerprint.as_str())
        .collect();

    let eligible = registry
        .sites
        .iter()
        .filter(|site| site.disposition == Disposition::Eligible)
        .count();
    let excluded = registry
        .sites
        .iter()
        .filter(|site| site.disposition == Disposition::Excluded)
        .count();
    let unreviewed = registry
        .sites
        .iter()
        .filter(|site| site.disposition == Disposition::Unreviewed)
        .count();
    let newly_found = scan
        .candidates
        .iter()
        .filter(|candidate| !registered.contains(candidate.fingerprint.as_str()))
        .count();
    let missing_legacy_anchors = registry
        .sites
        .iter()
        .filter(|site| {
            site.disposition == Disposition::Eligible
                && site.evidence.points() < 4
                && !current.contains(site.fingerprint.as_str())
        })
        .count();
    let earned_points: usize = registry
        .sites
        .iter()
        .filter(|site| site.disposition == Disposition::Eligible)
        .map(|site| site.evidence.points())
        .sum();
    let possible_points = eligible * 4;
    let coverage_percent =
        (possible_points > 0).then_some(earned_points as f64 * 100.0 / possible_points as f64);
    let provisional =
        unreviewed + newly_found + missing_legacy_anchors > 0 || !scan.parse_issues.is_empty();

    Ok(MetricReport {
        schema_version: SCHEMA_VERSION,
        root: scan.root.clone(),
        includes: scan.includes.clone(),
        scanned_candidates: scan.candidates.len(),
        registered_sites: registry.sites.len(),
        eligible,
        excluded,
        unreviewed,
        newly_found,
        missing_legacy_anchors,
        parse_issues: scan.parse_issues.clone(),
        earned_points,
        possible_points,
        coverage_percent,
        provisional,
    })
}

fn validate(root: &Path, registry: &Registry) -> Result<()> {
    ensure!(
        registry.schema_version == SCHEMA_VERSION,
        "unsupported registry schema version {}",
        registry.schema_version
    );
    let mut ids = HashSet::new();
    let mut fingerprints = HashSet::new();
    for site in &registry.sites {
        ensure!(!site.id.trim().is_empty(), "site id cannot be empty");
        ensure!(ids.insert(&site.id), "duplicate site id {}", site.id);
        ensure!(
            fingerprints.insert(&site.fingerprint),
            "duplicate fingerprint {}",
            site.fingerprint
        );
        match site.disposition {
            Disposition::Excluded => {
                ensure!(
                    site.reason
                        .as_ref()
                        .is_some_and(|reason| !reason.trim().is_empty()),
                    "excluded site {} requires a reason",
                    site.id
                );
                ensure!(
                    site.evidence.points() == 0,
                    "excluded site {} cannot earn evidence points",
                    site.id
                );
            }
            Disposition::Unreviewed => {
                ensure!(
                    site.evidence.points() == 0,
                    "unreviewed site {} cannot earn evidence points",
                    site.id
                );
            }
            Disposition::Eligible => {
                for (criterion, reference) in site.evidence.entries() {
                    if let Some(reference) = reference {
                        validate_reference(root, &site.id, criterion, reference)?;
                    }
                }
            }
        }
    }
    Ok(())
}

fn validate_reference(root: &Path, id: &str, criterion: &str, reference: &str) -> Result<()> {
    if reference.trim().is_empty() {
        bail!("site {id} has an empty {criterion} evidence reference");
    }
    let (path, needle) = reference.split_once('#').unwrap_or((reference, ""));
    let base = if root.is_file() {
        root.parent().expect("a source file has a parent")
    } else {
        root
    };
    let canonical_base = base.canonicalize()?;
    let evidence_file = base
        .join(path)
        .canonicalize()
        .with_context(|| format!("site {id} {criterion} evidence file does not exist: {path}"))?;
    ensure!(
        evidence_file.starts_with(canonical_base),
        "site {id} {criterion} evidence escapes the scanned root"
    );
    ensure!(
        evidence_file.is_file(),
        "site {id} {criterion} evidence is not a file"
    );
    if !needle.is_empty() {
        let source = fs::read_to_string(&evidence_file)
            .with_context(|| format!("cannot read site {id} {criterion} evidence file {path}"))?;
        ensure!(
            source.contains(needle),
            "site {id} {criterion} evidence marker not found: {reference}"
        );
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::fs;

    use tempfile::tempdir;

    use crate::model::{Disposition, Evidence, ParseIssue, Registry};
    use crate::scan::scan;

    use super::{measure, sync};

    #[test]
    fn denominator_survives_removal_of_original_if() {
        let dir = tempdir().unwrap();
        let source = dir.path().join("policy.py");
        fs::write(&source, "if ready:\n    promote()\n").unwrap();
        let initial = scan(dir.path(), &[]).unwrap();
        let mut registry = Registry::default();
        assert_eq!(sync(&initial, &mut registry, false).unwrap(), 1);
        assert_eq!(
            measure(dir.path(), &initial, &registry).unwrap().eligible,
            0
        );

        fs::write(
            &source,
            "class Context: pass\nclass Rules: pass\ndef test_outcomes(): pass\ndef test_trace(): pass\n",
        )
        .unwrap();
        registry.sites[0].id = "promotion-readiness".to_owned();
        registry.sites[0].disposition = Disposition::Eligible;
        registry.sites[0].evidence = Evidence {
            typed_context: Some("policy.py#Context".to_owned()),
            named_rules: Some("policy.py#Rules".to_owned()),
            outcomes_tested: Some("policy.py#test_outcomes".to_owned()),
            trace_tested: Some("policy.py#test_trace".to_owned()),
        };

        let after = scan(dir.path(), &[]).unwrap();
        let report = measure(dir.path(), &after, &registry).unwrap();
        assert_eq!(after.candidates.len(), 0);
        assert_eq!(report.eligible, 1);
        assert_eq!(report.earned_points, 4);
        assert_eq!(report.possible_points, 4);
        assert_eq!(report.coverage_percent, Some(100.0));
        assert!(!report.provisional);
    }

    #[test]
    fn new_sites_make_measurement_provisional_until_reviewed() {
        let dir = tempdir().unwrap();
        let source = dir.path().join("policy.py");
        fs::write(&source, "if a:\n    pass\n").unwrap();
        let mut registry = Registry::default();
        sync(&scan(dir.path(), &[]).unwrap(), &mut registry, false).unwrap();
        registry.sites[0].disposition = Disposition::Excluded;
        registry.sites[0].reason = Some("mechanical input validation".to_owned());
        fs::write(&source, "if a:\n    pass\nif b:\n    pass\n").unwrap();

        let scan = scan(dir.path(), &[]).unwrap();
        let report = measure(dir.path(), &scan, &registry).unwrap();
        assert_eq!(report.newly_found, 1);
        assert!(report.provisional);
        assert_eq!(sync(&scan, &mut registry, false).unwrap(), 1);
        let synced = measure(dir.path(), &scan, &registry).unwrap();
        assert_eq!(synced.newly_found, 0);
        assert_eq!(synced.unreviewed, 1);
    }

    #[test]
    fn partial_scan_needs_explicit_sync_override() {
        let dir = tempdir().unwrap();
        fs::write(dir.path().join("policy.py"), "if ready:\n    pass\n").unwrap();
        let mut report = scan(dir.path(), &[]).unwrap();
        report.parse_issues.push(ParseIssue {
            path: "other.swift".to_owned(),
            message: "syntax error".to_owned(),
        });
        let mut registry = Registry::default();
        assert!(sync(&report, &mut registry, false).is_err());
        assert_eq!(sync(&report, &mut registry, true).unwrap(), 1);
        assert!(measure(dir.path(), &report, &registry).unwrap().provisional);
    }
}
