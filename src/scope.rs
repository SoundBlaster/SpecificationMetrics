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
}

impl SourceRole {
    fn label(self) -> &'static str {
        match self {
            Self::Application => "application",
            Self::Framework => "framework",
            Self::Test => "test",
            Self::Generated => "generated",
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
}

pub struct ScopeManifest {
    entries: Vec<(String, SourceRole)>,
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
            for path in source_set.paths {
                entries.push((normalize_path(&path)?, source_set.role));
            }
        }
        ensure!(
            entries
                .iter()
                .any(|(_, role)| *role == SourceRole::Application),
            "scope manifest needs an application source set"
        );
        entries.sort();
        entries.dedup();
        let mut hasher = blake3::Hasher::new();
        hasher.update(&SCOPE_SCHEMA_VERSION.to_le_bytes());
        for (path, role) in &entries {
            hasher.update(path.as_bytes());
            hasher.update(&[0]);
            hasher.update(role.label().as_bytes());
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
        for (prefix, role) in &self.entries {
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
    let path = raw.trim().trim_end_matches('/').replace('\\', "/");
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
}
