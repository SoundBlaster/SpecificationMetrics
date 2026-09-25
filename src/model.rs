use serde::{Deserialize, Serialize};

pub const SCHEMA_VERSION: u32 = 1;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Language {
    Python,
    Swift,
    Rust,
}

impl Language {
    pub fn from_extension(extension: &str) -> Option<Self> {
        match extension {
            "py" => Some(Self::Python),
            "swift" => Some(Self::Swift),
            "rs" => Some(Self::Rust),
            _ => None,
        }
    }

    pub fn label(self) -> &'static str {
        match self {
            Self::Python => "python",
            Self::Swift => "swift",
            Self::Rust => "rust",
        }
    }
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Candidate {
    pub fingerprint: String,
    pub language: Language,
    pub path: String,
    pub kind: String,
    pub line: usize,
    pub column: usize,
    pub excerpt: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ParseIssue {
    pub path: String,
    pub message: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct ScanReport {
    pub schema_version: u32,
    pub root: String,
    pub includes: Vec<String>,
    pub candidates: Vec<Candidate>,
    pub parse_issues: Vec<ParseIssue>,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Disposition {
    Unreviewed,
    Eligible,
    Excluded,
}

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct Evidence {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub typed_context: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub named_rules: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub outcomes_tested: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub trace_tested: Option<String>,
}

impl Evidence {
    pub fn entries(&self) -> [(&'static str, Option<&str>); 4] {
        [
            ("typed_context", self.typed_context.as_deref()),
            ("named_rules", self.named_rules.as_deref()),
            ("outcomes_tested", self.outcomes_tested.as_deref()),
            ("trace_tested", self.trace_tested.as_deref()),
        ]
    }

    pub fn points(&self) -> usize {
        self.entries()
            .iter()
            .filter(|(_, reference)| reference.is_some_and(|text| !text.trim().is_empty()))
            .count()
    }
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Site {
    pub id: String,
    pub fingerprint: String,
    pub language: Language,
    pub path: String,
    pub kind: String,
    pub disposition: Disposition,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
    #[serde(default, skip_serializing_if = "evidence_is_empty")]
    pub evidence: Evidence,
}

fn evidence_is_empty(evidence: &Evidence) -> bool {
    evidence.points() == 0
}

impl Site {
    pub fn unreviewed(candidate: &Candidate) -> Self {
        Self {
            id: candidate.fingerprint.clone(),
            fingerprint: candidate.fingerprint.clone(),
            language: candidate.language,
            path: candidate.path.clone(),
            kind: candidate.kind.clone(),
            disposition: Disposition::Unreviewed,
            reason: None,
            evidence: Evidence::default(),
        }
    }
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Registry {
    pub schema_version: u32,
    #[serde(default)]
    pub includes: Vec<String>,
    #[serde(default)]
    pub sites: Vec<Site>,
}

impl Default for Registry {
    fn default() -> Self {
        Self {
            schema_version: SCHEMA_VERSION,
            includes: Vec::new(),
            sites: Vec::new(),
        }
    }
}

#[derive(Debug, Serialize)]
pub struct MetricReport {
    pub schema_version: u32,
    pub root: String,
    pub includes: Vec<String>,
    pub scanned_candidates: usize,
    pub registered_sites: usize,
    pub eligible: usize,
    pub excluded: usize,
    pub unreviewed: usize,
    pub newly_found: usize,
    pub missing_legacy_anchors: usize,
    pub parse_issues: Vec<ParseIssue>,
    pub earned_points: usize,
    pub possible_points: usize,
    pub coverage_percent: Option<f64>,
    pub provisional: bool,
}
