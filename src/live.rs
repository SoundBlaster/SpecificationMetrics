use std::collections::HashSet;
use std::path::Path;
use std::process::Command;

use anyhow::{Result, ensure};

use crate::model::{
    COUNTING_RULE_VERSION, Disposition, LiveMetricReport, LiveState, Registry, SCHEMA_VERSION,
    ScanReport,
};

pub fn measure(scan: &ScanReport, registry: Option<&Registry>) -> Result<LiveMetricReport> {
    let mut excluded = HashSet::new();
    if let Some(registry) = registry {
        ensure!(
            registry.schema_version == SCHEMA_VERSION,
            "unsupported registry schema version {}",
            registry.schema_version
        );
        ensure!(
            registry.includes == scan.includes,
            "scan scope does not match registry includes"
        );
        let mut fingerprints = HashSet::new();
        for site in &registry.sites {
            ensure!(
                fingerprints.insert(site.fingerprint.as_str()),
                "duplicate registry fingerprint {}",
                site.fingerprint
            );
            if site.disposition == Disposition::Excluded {
                ensure!(
                    site.reason
                        .as_ref()
                        .is_some_and(|reason| !reason.trim().is_empty()),
                    "excluded site {} requires a reason",
                    site.id
                );
                excluded.insert(site.fingerprint.as_str());
            }
        }
    }

    let specifications: HashSet<String> = scan
        .specifications
        .iter()
        .map(|spec| {
            format!(
                "{}:{}:{}:{}:{}:{}",
                spec.language.label(),
                spec.path,
                spec.kind,
                spec.name,
                spec.line,
                spec.column
            )
        })
        .collect();
    let covered_candidates = scan
        .candidates
        .iter()
        .filter(|candidate| candidate.inside_specification)
        .count();
    let reviewed_exclusions = scan
        .candidates
        .iter()
        .filter(|candidate| {
            !candidate.inside_specification && excluded.contains(candidate.fingerprint.as_str())
        })
        .count();
    let remaining_opportunities = scan.candidates.len() - covered_candidates - reviewed_exclusions;
    let specification_definitions = specifications.len();
    let state = match (specification_definitions, remaining_opportunities) {
        (_, remaining) if remaining > 0 => LiveState::Ratio,
        (specifications, 0) if specifications > 0 => LiveState::Complete,
        _ => LiveState::NotApplicable,
    };
    let ratio = (remaining_opportunities > 0)
        .then_some(specification_definitions as f64 / remaining_opportunities as f64);

    Ok(LiveMetricReport {
        schema_version: SCHEMA_VERSION,
        counting_rule_version: COUNTING_RULE_VERSION,
        root: scan.root.clone(),
        includes: scan.includes.clone(),
        source_revision: source_revision(Path::new(&scan.root)),
        source_digest: scan.source_digest.clone(),
        scanned_candidates: scan.candidates.len(),
        covered_candidates,
        reviewed_exclusions,
        specification_definitions,
        remaining_opportunities,
        ratio,
        state,
        provisional: !scan.parse_issues.is_empty(),
        parse_issues: scan.parse_issues.clone(),
    })
}

fn source_revision(root: &Path) -> Option<String> {
    let directory = if root.is_file() { root.parent()? } else { root };
    let output = Command::new("git")
        .arg("-C")
        .arg(directory)
        .args(["rev-parse", "--verify", "HEAD"])
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let revision = String::from_utf8(output.stdout).ok()?;
    let revision = revision.trim();
    (!revision.is_empty()).then(|| revision.to_owned())
}

#[cfg(test)]
mod tests {
    use std::fs;

    use tempfile::tempdir;

    use crate::model::{Disposition, LiveState, Registry};
    use crate::scan::scan;

    use super::measure;

    #[test]
    fn ratio_is_recomputed_from_current_source() {
        let dir = tempdir().unwrap();
        let source = dir.path().join("policy.py");
        fs::write(&source, "if ready:\n    promote()\n").unwrap();
        let first = measure(&scan(dir.path(), &[]).unwrap(), None).unwrap();
        assert_eq!(first.specification_definitions, 0);
        assert_eq!(first.remaining_opportunities, 1);
        assert_eq!(first.ratio, Some(0.0));

        fs::write(
            &source,
            "class Ready(Specification):\n    def is_satisfied_by(self, value):\n        if value:\n            return True\n        return False\n",
        )
        .unwrap();
        let converted = measure(&scan(dir.path(), &[]).unwrap(), None).unwrap();
        assert_eq!(converted.specification_definitions, 1);
        assert_eq!(converted.covered_candidates, 1);
        assert_eq!(converted.remaining_opportunities, 0);
        assert_eq!(converted.state, LiveState::Complete);
        assert_eq!(converted.ratio, None);

        fs::write(
            &source,
            "class Ready(Specification):\n    def is_satisfied_by(self, value):\n        if value:\n            return True\n        return False\nif other:\n    promote()\n",
        )
        .unwrap();
        let later = measure(&scan(dir.path(), &[]).unwrap(), None).unwrap();
        assert_eq!(later.specification_definitions, 1);
        assert_eq!(later.remaining_opportunities, 1);
        assert_eq!(later.ratio, Some(1.0));

        fs::write(
            &source,
            "class Ready(Specification):\n    pass\nclass Allowed(Specification):\n    pass\nif other:\n    promote()\n",
        )
        .unwrap();
        let above_one = measure(&scan(dir.path(), &[]).unwrap(), None).unwrap();
        assert_eq!(above_one.specification_definitions, 2);
        assert_eq!(above_one.remaining_opportunities, 1);
        assert_eq!(above_one.ratio, Some(2.0));
    }

    #[test]
    fn no_specifications_and_no_candidates_is_not_applicable() {
        let dir = tempdir().unwrap();
        fs::write(dir.path().join("empty.py"), "pass\n").unwrap();
        let report = measure(&scan(dir.path(), &[]).unwrap(), None).unwrap();
        assert_eq!(report.state, LiveState::NotApplicable);
        assert_eq!(report.ratio, None);
    }

    #[test]
    fn only_current_reviewed_exclusions_reduce_denominator() {
        let dir = tempdir().unwrap();
        let source = dir.path().join("policy.py");
        fs::write(&source, "if first:\n    pass\nif second:\n    pass\n").unwrap();
        let initial = scan(dir.path(), &[]).unwrap();
        let mut registry = Registry::default();
        let first = crate::model::Site::unreviewed(&initial.candidates[0]);
        registry.sites.push(first);
        registry.sites[0].disposition = Disposition::Excluded;
        registry.sites[0].reason = Some("mechanical guard".to_owned());
        let measured = measure(&initial, Some(&registry)).unwrap();
        assert_eq!(measured.remaining_opportunities, 1);
        assert_eq!(measured.reviewed_exclusions, 1);

        fs::write(&source, "if replacement:\n    pass\nif second:\n    pass\n").unwrap();
        let rescanned = measure(&scan(dir.path(), &[]).unwrap(), Some(&registry)).unwrap();
        assert_eq!(rescanned.remaining_opportunities, 2);
        assert_eq!(rescanned.reviewed_exclusions, 0);
    }

    #[test]
    fn same_named_declarations_in_different_scopes_count_separately() {
        let dir = tempdir().unwrap();
        fs::write(
            dir.path().join("policy.py"),
            "class A:\n    class Rule(Specification):\n        pass\nclass B:\n    class Rule(Specification):\n        pass\n",
        )
        .unwrap();

        let scan = scan(dir.path(), &[]).unwrap();
        assert!(scan.parse_issues.is_empty(), "{:?}", scan.parse_issues);
        assert_eq!(scan.specifications.len(), 2);
        let measured = measure(&scan, None).unwrap();
        assert_eq!(measured.specification_definitions, 2);
        assert_eq!(measured.state, LiveState::Complete);
    }
}
