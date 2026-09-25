use std::fs;
use std::path::{Component, Path};

use anyhow::{Context, Result, ensure};
use serde::{Deserialize, Serialize};

const SCOPE_SCHEMA_VERSION: u32 = 1;

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SourceRole {
    Application,
    Framework,
    Test,
    Generated,
    Excluded,
}

impl SourceRole {
    fn label(self) -> &'static str {
        match self {
            Self::Application => "application",
            Self::Framework => "framework",
            Self::Test => "test",
            Self::Generated => "generated",
            Self::Excluded => "excluded",
        }
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ScopeDocument {
    schema_version: u32,
    source_sets: Vec<SourceSet>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct SourceSet {
    role: SourceRole,
    paths: Vec<String>,
    reason: Option<String>,
}

pub struct ScopeManifest {
    entries: Vec<(String, SourceRole, Option<String>)>,
    digest: String,
}

impl ScopeManifest {
    pub fn load(path: &Path) -> Result<Self> {
        let source = fs::read_to_string(path)
            .with_context(|| format!("cannot read scope manifest {}", path.display()))?;
        Self::parse(&source).with_context(|| format!("invalid scope manifest {}", path.display()))
    }

    pub fn parse(source: &str) -> Result<Self> {
        let document: ScopeDocument = toml::from_str(source)?;
        ensure!(
            document.schema_version == SCOPE_SCHEMA_VERSION,
            "unsupported scope manifest schema version {}",
            document.schema_version
        );
        let mut entries = Vec::new();
        for source_set in document.source_sets {
            ensure!(!source_set.paths.is_empty(), "source set has no paths");
            let reason = source_set.reason.map(|reason| reason.trim().to_owned());
            ensure!(
                reason.as_ref().is_none_or(|reason| !reason.is_empty()),
                "source set reason cannot be empty"
            );
            ensure!(
                source_set.role != SourceRole::Excluded || reason.is_some(),
                "excluded source set requires a reason"
            );
            for path in source_set.paths {
                entries.push((normalize_path(&path)?, source_set.role, reason.clone()));
            }
        }
        ensure!(
            entries
                .iter()
                .any(|(_, role, _)| *role == SourceRole::Application),
            "scope manifest needs an application source set"
        );
        entries.sort();
        entries.dedup();
        ensure!(
            !entries.windows(2).any(|pair| pair[0].0 == pair[1].0
                && pair[0].1 == pair[1].1
                && pair[0].2 != pair[1].2),
            "same source path and role have conflicting reasons"
        );
        let mut hasher = blake3::Hasher::new();
        hasher.update(&SCOPE_SCHEMA_VERSION.to_le_bytes());
        for (path, role, reason) in &entries {
            hasher.update(path.as_bytes());
            hasher.update(&[0]);
            hasher.update(role.label().as_bytes());
            hasher.update(&[0]);
            hasher.update(reason.as_deref().unwrap_or("").as_bytes());
            hasher.update(&[0]);
        }
        Ok(Self {
            entries,
            digest: hasher.finalize().to_hex().to_string(),
        })
    }

    pub fn digest(&self) -> &str {
        &self.digest
    }

    pub fn role_for(&self, path: &str) -> Result<SourceRole, String> {
        let mut selected = None;
        let mut specificity = 0;
        for (prefix, role, _) in &self.entries {
            if prefix != "." && path != prefix && !path.starts_with(&format!("{prefix}/")) {
                continue;
            }
            let candidate_specificity = if prefix == "." { 0 } else { prefix.len() };
            if selected.is_none() || candidate_specificity > specificity {
                selected = Some(*role);
                specificity = candidate_specificity;
            } else if candidate_specificity == specificity && selected != Some(*role) {
                return Err("conflicting source roles at the same path".to_owned());
            }
        }
        selected.ok_or_else(|| "source file has no role in scope manifest".to_owned())
    }
}

fn normalize_path(raw: &str) -> Result<String> {
    let converted = raw.trim().replace('\\', "/");
    let path = converted.trim_end_matches('/').to_owned();
    ensure!(!path.is_empty(), "source path cannot be empty");
    if path == "." {
        return Ok(path);
    }
    let value = Path::new(&path);
    ensure!(
        !path.contains("//")
            && !value.is_absolute()
            && value
                .components()
                .all(|part| matches!(part, Component::Normal(_))),
        "source path must be repository-relative: {path}"
    );
    Ok(path)
}

#[cfg(test)]
mod tests {
    use super::{ScopeManifest, SourceRole};

    #[test]
    fn most_specific_role_wins_and_manifest_digest_is_semantic() {
        let first = ScopeManifest::parse(
            "schema_version = 1\n[[source_sets]]\nrole = 'application'\npaths = ['.']\n[[source_sets]]\nrole = 'test'\npaths = ['tests']\n",
        )
        .unwrap();
        let reordered = ScopeManifest::parse(
            "schema_version=1\n[[source_sets]]\nrole='test'\npaths=['tests']\n[[source_sets]]\nrole='application'\npaths=['.']\n",
        )
        .unwrap();
        assert_eq!(first.digest(), reordered.digest());
        let changed_role = ScopeManifest::parse(
            "schema_version=1\n[[source_sets]]\nrole='application'\npaths=['.']\n[[source_sets]]\nrole='generated'\npaths=['tests']\n",
        )
        .unwrap();
        assert_ne!(first.digest(), changed_role.digest());
        assert_eq!(first.role_for("src/main.rs"), Ok(SourceRole::Application));
        assert_eq!(first.role_for("tests/test.py"), Ok(SourceRole::Test));
    }

    #[test]
    fn windows_trailing_separator_preserves_directory_role() {
        let manifest = ScopeManifest::parse(
            "schema_version=1\n[[source_sets]]\nrole='application'\npaths=['.']\n[[source_sets]]\nrole='test'\npaths=['tests\\\\']\n",
        )
        .unwrap();
        let canonical = ScopeManifest::parse(
            "schema_version=1\n[[source_sets]]\nrole='application'\npaths=['.']\n[[source_sets]]\nrole='test'\npaths=['tests']\n",
        )
        .unwrap();
        assert_eq!(manifest.role_for("tests/nested.py"), Ok(SourceRole::Test));
        assert_eq!(manifest.digest(), canonical.digest());
    }

    #[test]
    fn missing_and_conflicting_roles_are_reported() {
        let missing = ScopeManifest::parse(
            "schema_version=1\n[[source_sets]]\nrole='application'\npaths=['src']\n",
        )
        .unwrap();
        assert!(missing.role_for("other.py").is_err());
        let conflict = ScopeManifest::parse(
            "schema_version=1\n[[source_sets]]\nrole='application'\npaths=['src']\n[[source_sets]]\nrole='test'\npaths=['src']\n",
        )
        .unwrap();
        assert!(conflict.role_for("src/main.py").is_err());
        assert!(
            ScopeManifest::parse(
                "schema_version=1\n[[source_sets]]\nrole='application'\npaths=['src//bad']\n"
            )
            .is_err()
        );
    }

    #[test]
    fn explicit_file_and_directory_exclusions_require_a_reason() {
        let manifest = ScopeManifest::parse(
            "schema_version=1\n[[source_sets]]\nrole='application'\npaths=['.']\n[[source_sets]]\nrole='excluded'\npaths=['app/legacy.py', 'old']\nreason='Outside current adoption scope'\n",
        )
        .unwrap();
        assert_eq!(manifest.role_for("app/legacy.py"), Ok(SourceRole::Excluded));
        assert_eq!(
            manifest.role_for("old/nested/rule.rs"),
            Ok(SourceRole::Excluded)
        );
        assert_eq!(
            manifest.role_for("app/current.py"),
            Ok(SourceRole::Application)
        );
        let changed_reason = ScopeManifest::parse(
            "schema_version=1\n[[source_sets]]\nrole='application'\npaths=['.']\n[[source_sets]]\nrole='excluded'\npaths=['app/legacy.py', 'old']\nreason='Reviewed later'\n",
        )
        .unwrap();
        assert_ne!(manifest.digest(), changed_reason.digest());
        assert!(ScopeManifest::parse(
            "schema_version=1\n[[source_sets]]\nrole='application'\npaths=['.']\n[[source_sets]]\nrole='excluded'\npaths=['old']\n"
        )
        .is_err());
    }
}
