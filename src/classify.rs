use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result, bail, ensure};
use reqwest::Url;
use reqwest::blocking::{Client, Response};
use reqwest::header::{AUTHORIZATION, CONTENT_TYPE};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use tree_sitter::{Node, Parser};

use crate::metric;
use crate::model::{Candidate, Disposition, Language, ScanReport};
use crate::{scan, scope};

const ADAPTER_VERSION: &str = "1.0.0";
const MAX_PROFILE_BYTES: usize = 4 * 1024;
const MAX_CONTEXT_BYTES: usize = 24 * 1024;
const MAX_DECLARATION_BYTES: usize = 12 * 1024;
const MAX_EXCERPT_BYTES: usize = 4 * 1024;
const MAX_RELATED_SITE_BYTES: usize = 1024;
const MAX_RESPONSE_BYTES: u64 = 1024 * 1024;

const PROMPT_CONTRACT: &str = "SpecificationMetrics Jev Choice adapter v1. Return one choice for each named question. The opportunity axis estimates whether this source site belongs in the Specification opportunity denominator. The concern_kind axis describes the kind of logic. The axes are independent. Use needs_review or unknown when the bounded evidence is insufficient. Do not infer hidden context.";

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct ArchitectureProfile {
    id: String,
    version: String,
    purpose: String,
    preferred_patterns: Vec<String>,
    boundaries: Vec<String>,
    mechanical_exclusions: Vec<MechanicalExclusion>,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct MechanicalExclusion {
    construct: String,
    reason: String,
}

#[derive(Debug, Serialize)]
struct Rubric {
    id: &'static str,
    version: u32,
    opportunity_definitions: BTreeMap<&'static str, &'static str>,
    concern_kind_definitions: BTreeMap<&'static str, &'static str>,
}

#[derive(Debug, Serialize)]
pub(crate) struct ClassificationReport {
    artifact_kind: &'static str,
    schema_version: u32,
    run_id: String,
    generated_at: String,
    source: SourceProvenance,
    rubric: DigestRef,
    architecture_profile: ProfileRef,
    provider: ProviderProvenance,
    suggestions: Vec<Suggestion>,
}

pub(crate) struct ClassifyOptions<'a> {
    pub scan_path: &'a Path,
    pub profile_path: &'a Path,
    pub registry_path: Option<&'a Path>,
    pub manifest_path: Option<&'a Path>,
    pub endpoint: &'a str,
    pub model: &'a str,
    pub api_key_env: &'a str,
    pub allow_hosted: bool,
    pub timeout_seconds: u64,
    pub min_confidence: Option<f64>,
}

#[derive(Debug, Serialize)]
struct SourceProvenance {
    revision: Option<String>,
    source_digest: String,
    scope_manifest_digest: Option<String>,
    scan_report_digest: String,
}

#[derive(Debug, Serialize)]
struct DigestRef {
    id: &'static str,
    version: u32,
    digest: String,
}

#[derive(Debug, Serialize)]
struct ProfileRef {
    id: String,
    version: String,
    digest: String,
}

#[derive(Debug, Serialize)]
struct ProviderProvenance {
    id: &'static str,
    endpoint: String,
    requested_model: String,
    returned_models: Vec<String>,
    adapter_version: &'static str,
    prompt_digest: String,
    inference_config_digest: String,
    inference_parameters: InferenceParameters,
    data_boundary: &'static str,
    usage: Usage,
}

#[derive(Debug, Serialize)]
struct InferenceParameters {
    temperature: Option<f64>,
    top_p: Option<f64>,
    max_output_tokens: Option<u32>,
    provider_options_digest: Option<String>,
    min_confidence: Option<f64>,
    timeout_seconds: u64,
}

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
struct Usage {
    input_tokens: u64,
    output_tokens: u64,
}

#[derive(Debug, Serialize)]
struct Suggestion {
    candidate_fingerprint: String,
    context_digest: String,
    model_id: Option<String>,
    model_revision: Option<String>,
    cacheable: bool,
    opportunity: Opportunity,
    concern_kind: ConcernKind,
    diagnostics: Vec<Diagnostic>,
    opportunity_rationale: Rationale,
    concern_rationale: Rationale,
    provider_scores: ProviderScores,
    score_semantics: ScoreSemantics,
}

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
enum Opportunity {
    Eligible,
    Excluded,
    NeedsReview,
}

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
enum ConcernKind {
    Policy,
    Mechanics,
    VariantBehavior,
    Unknown,
}

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
enum Diagnostic {
    ProviderError,
    MalformedProviderOutput,
    CloseDecision,
}

#[derive(Debug, Serialize)]
struct Rationale {
    text: Option<String>,
    source: &'static str,
}

#[derive(Debug, Serialize)]
struct ProviderScores {
    opportunity: Option<ChoiceScores>,
    concern_kind: Option<ChoiceScores>,
}

#[derive(Debug, Serialize)]
struct ChoiceScores {
    probabilities: BTreeMap<String, f64>,
    confidence: Option<f64>,
}

#[derive(Debug, Serialize)]
struct ScoreSemantics {
    opportunity: Option<&'static str>,
    concern_kind: Option<&'static str>,
}

#[derive(Debug, Serialize)]
struct CandidateContext {
    fingerprint: String,
    language: Language,
    path: String,
    position: Position,
    construct_kind: String,
    excerpt: String,
    excerpt_truncated: bool,
    enclosing_symbol: Option<String>,
    enclosing_source: Option<String>,
    enclosing_source_truncated: bool,
    related_sites: Vec<RelatedSite>,
}

#[derive(Debug, Serialize)]
struct Position {
    start_line: usize,
    start_column: usize,
    end_line: usize,
    end_column: usize,
}

#[derive(Debug, Serialize)]
struct RelatedSite {
    fingerprint: String,
    language: Language,
    path: String,
    symbol: Option<String>,
    construct_kind: String,
    excerpt: String,
    excerpt_truncated: bool,
}

#[derive(Debug, Deserialize)]
struct JevResponse {
    model: String,
    answers: HashMap<String, JevAnswer>,
    usage: Usage,
}

#[derive(Debug, Deserialize)]
struct JevAnswer {
    #[serde(rename = "type")]
    answer_type: String,
    choice: String,
    confidence: f64,
    probabilities: BTreeMap<String, f64>,
}

pub(crate) struct JevClient {
    client: Client,
    endpoint: String,
    model: String,
    bearer_token: String,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum JevError {
    Provider,
    Malformed,
}

impl JevClient {
    pub(crate) fn new(
        endpoint: &str,
        model: &str,
        token: String,
        timeout: Duration,
    ) -> Result<Self> {
        validate_endpoint(endpoint)?;
        ensure!(!model.trim().is_empty(), "Jev model cannot be empty");
        let client = Client::builder()
            .timeout(timeout)
            .redirect(reqwest::redirect::Policy::none())
            .retry(reqwest::retry::never())
            .build()
            .context("cannot build Jev HTTP client")?;
        Ok(Self {
            client,
            endpoint: endpoint.to_owned(),
            model: model.to_owned(),
            bearer_token: token,
        })
    }

    fn classify(
        &self,
        context: &CandidateContext,
        profile: &ArchitectureProfile,
    ) -> std::result::Result<JevResponse, JevError> {
        let state = json!({
            "candidate": context,
            "architecture_profile": profile,
        });
        parse_response_body(&self.request(&state, &choice_questions())?)
    }

    pub(crate) fn requested_model(&self) -> &str {
        &self.model
    }

    pub(crate) fn request(
        &self,
        state: &Value,
        questions: &Value,
    ) -> std::result::Result<Vec<u8>, JevError> {
        let body = json!({
            "model": self.model,
            "state": state,
            "questions": questions
        });
        let mut response = self
            .client
            .post(&self.endpoint)
            .header(AUTHORIZATION, format!("Bearer {}", self.bearer_token))
            .header(CONTENT_TYPE, "application/json")
            .json(&body)
            .send()
            .map_err(|_| JevError::Provider)?;
        if !response.status().is_success() {
            return Err(JevError::Provider);
        }
        bounded_response_body(&mut response)
    }
}

fn parse_response_body(bytes: &[u8]) -> std::result::Result<JevResponse, JevError> {
    serde_json::from_slice(bytes).map_err(|_| JevError::Malformed)
}

pub(crate) fn classify(options: ClassifyOptions<'_>) -> Result<ClassificationReport> {
    let ClassifyOptions {
        scan_path,
        profile_path,
        registry_path,
        manifest_path,
        endpoint,
        model,
        api_key_env,
        allow_hosted,
        timeout_seconds,
        min_confidence,
    } = options;
    ensure!(
        allow_hosted,
        "hosted classification requires --allow-hosted-classification"
    );
    ensure!(timeout_seconds > 0, "timeout must be greater than zero");
    if let Some(threshold) = min_confidence {
        ensure!(
            (0.0..=1.0).contains(&threshold),
            "--min-confidence must be between 0 and 1"
        );
    }
    ensure!(
        !api_key_env.trim().is_empty(),
        "API key environment variable name cannot be empty"
    );

    let scan_bytes = fs::read(scan_path)
        .with_context(|| format!("cannot read scan report {}", scan_path.display()))?;
    let saved_scan: ScanReport = serde_json::from_slice(&scan_bytes)
        .with_context(|| format!("invalid scan report {}", scan_path.display()))?;
    let manifest = manifest_path.map(scope::ScopeManifest::load).transpose()?;
    if saved_scan.scope_manifest_digest.is_some() {
        ensure!(
            manifest.is_some(),
            "the scan used a scope manifest; pass it with --scope-manifest"
        );
    }
    ensure!(
        saved_scan.scope_manifest_digest.as_deref()
            == manifest.as_ref().map(|value| value.digest()),
        "scope manifest does not match the saved scan report"
    );
    let root = PathBuf::from(&saved_scan.root);
    let fresh_scan = scan::scan_with_scope(&root, &saved_scan.includes, manifest.as_ref())?;
    verify_scan_snapshot(&saved_scan, &fresh_scan)?;

    let profile_bytes = fs::read(profile_path).with_context(|| {
        format!(
            "cannot read architecture profile {}",
            profile_path.display()
        )
    })?;
    let profile: ArchitectureProfile = toml::from_str(
        std::str::from_utf8(&profile_bytes).context("architecture profile is not UTF-8")?,
    )
    .with_context(|| format!("invalid architecture profile {}", profile_path.display()))?;
    validate_profile(&profile)?;
    let profile_json = serde_json::to_vec(&profile)?;
    ensure!(
        profile_json.len() <= MAX_PROFILE_BYTES,
        "serialized architecture profile exceeds 4 KiB"
    );

    let token = std::env::var(api_key_env)
        .with_context(|| format!("API key environment variable {api_key_env} is not set"))?;
    ensure!(
        !token.is_empty(),
        "API key environment variable {api_key_env} is empty"
    );
    let jev = JevClient::new(endpoint, model, token, Duration::from_secs(timeout_seconds))?;
    let rubric = rubric();
    let rubric_digest = digest("blake3", &serde_json::to_vec(&rubric)?);
    let profile_digest = digest("blake3", &profile_bytes);
    let prompt_digest = digest("blake3", &serde_json::to_vec(&choice_questions())?);
    let inference_parameters = InferenceParameters {
        temperature: None,
        top_p: None,
        max_output_tokens: None,
        provider_options_digest: None,
        min_confidence,
        timeout_seconds,
    };
    let inference_config_digest = digest(
        "blake3",
        &serde_json::to_vec(&json!({
            "endpoint": endpoint,
            "requested_model": model,
            "parameters": inference_parameters,
            "redirects": "disabled",
            "automatic_retries": false,
        }))?,
    );
    let registry = registry_path
        .map(metric::load_existing_registry)
        .transpose()?;
    if let Some(registry) = &registry {
        ensure!(
            registry.includes == saved_scan.includes,
            "registry scope does not match the saved scan"
        );
        ensure!(
            registry.scope_manifest_digest == saved_scan.scope_manifest_digest,
            "registry scope manifest does not match the saved scan"
        );
    }
    let reviewed: BTreeSet<&str> = registry
        .iter()
        .flat_map(|value| &value.sites)
        .filter(|site| site.disposition != Disposition::Unreviewed)
        .map(|site| site.fingerprint.as_str())
        .collect();
    let snapshots: HashMap<&str, &[u8]> = fresh_scan
        .sources
        .iter()
        .map(|source| (source.path.as_str(), source.bytes.as_slice()))
        .collect();

    let mut suggestions = Vec::new();
    let mut actual_models = BTreeSet::new();
    let mut total_usage = Usage::default();
    let candidates: Vec<&Candidate> = fresh_scan
        .candidates
        .iter()
        .filter(|candidate| !candidate.inside_specification)
        .filter(|candidate| !reviewed.contains(candidate.fingerprint.as_str()))
        .collect();
    for candidate in &candidates {
        let context = build_context(candidate, &fresh_scan.candidates, &snapshots)?;
        let normalized_context = serde_json::to_value(&context)?;
        let context_digest = digest("blake3", &serde_json::to_vec(&normalized_context)?);
        let result = jev.classify(&context, &profile);
        let suggestion = match result {
            Ok(response) => {
                if !response.model.trim().is_empty() {
                    actual_models.insert(response.model.clone());
                }
                total_usage.input_tokens = total_usage
                    .input_tokens
                    .saturating_add(response.usage.input_tokens);
                total_usage.output_tokens = total_usage
                    .output_tokens
                    .saturating_add(response.usage.output_tokens);
                suggestion_from_response(candidate, context_digest, response, min_confidence)
            }
            Err(JevError::Provider) => {
                fallback_suggestion(candidate, context_digest, Diagnostic::ProviderError)
            }
            Err(JevError::Malformed) => fallback_suggestion(
                candidate,
                context_digest,
                Diagnostic::MalformedProviderOutput,
            ),
        };
        suggestions.push(suggestion);
    }

    let source_revision = git_revision(&root);
    let generated_at = time::OffsetDateTime::now_utc()
        .format(&time::format_description::well_known::Rfc3339)
        .context("cannot format classification timestamp")?;
    let run_id = make_run_id(&generated_at, &saved_scan.source_digest, &profile_digest);
    Ok(ClassificationReport {
        artifact_kind: "candidate_classification_suggestions",
        schema_version: 1,
        run_id,
        generated_at,
        source: SourceProvenance {
            revision: source_revision,
            source_digest: format!("blake3:{}", saved_scan.source_digest),
            scope_manifest_digest: saved_scan
                .scope_manifest_digest
                .map(|value| format!("blake3:{value}")),
            scan_report_digest: digest("blake3", &scan_bytes),
        },
        rubric: DigestRef {
            id: rubric.id,
            version: rubric.version,
            digest: rubric_digest,
        },
        architecture_profile: ProfileRef {
            id: profile.id,
            version: profile.version,
            digest: profile_digest,
        },
        provider: ProviderProvenance {
            id: "jev",
            endpoint: endpoint.to_owned(),
            requested_model: model.to_owned(),
            returned_models: actual_models.into_iter().collect(),
            adapter_version: ADAPTER_VERSION,
            prompt_digest,
            inference_config_digest,
            inference_parameters,
            data_boundary: "hosted",
            usage: total_usage,
        },
        suggestions,
    })
}

fn verify_scan_snapshot(saved: &ScanReport, fresh: &ScanReport) -> Result<()> {
    ensure!(
        saved.schema_version == fresh.schema_version,
        "scan schema version changed; rescan before classifying"
    );
    ensure!(
        saved.root == fresh.root,
        "scan root changed; rescan before classifying"
    );
    ensure!(
        saved.includes == fresh.includes,
        "scan includes changed; rescan before classifying"
    );
    ensure!(
        saved.scope_manifest_digest == fresh.scope_manifest_digest,
        "scan scope changed; rescan before classifying"
    );
    ensure!(
        saved.source_digest == fresh.source_digest,
        "source changed after scan; create a fresh scan report"
    );
    ensure!(
        saved.candidates.len() == fresh.candidates.len(),
        "candidate inventory changed after scan; create a fresh scan report"
    );
    for (old, new) in saved.candidates.iter().zip(&fresh.candidates) {
        ensure!(
            old == new,
            "candidate inventory or metadata changed after scan; create a fresh scan report"
        );
    }
    Ok(())
}

fn validate_profile(profile: &ArchitectureProfile) -> Result<()> {
    ensure!(
        !profile.id.trim().is_empty(),
        "architecture profile id cannot be empty"
    );
    ensure!(
        !profile.version.trim().is_empty(),
        "architecture profile version cannot be empty"
    );
    ensure!(
        !profile.purpose.trim().is_empty(),
        "architecture profile purpose cannot be empty"
    );
    ensure!(
        profile.preferred_patterns.len() <= 4,
        "architecture profile allows at most four preferred_patterns"
    );
    ensure!(
        profile.boundaries.len() <= 4,
        "architecture profile allows at most four boundaries"
    );
    ensure!(
        profile.mechanical_exclusions.len() <= 4,
        "architecture profile allows at most four mechanical_exclusions"
    );
    Ok(())
}

fn validate_endpoint(endpoint: &str) -> Result<()> {
    let url = Url::parse(endpoint).context("invalid Jev endpoint URL")?;
    let local_http = url.scheme() == "http"
        && matches!(url.host_str(), Some("localhost" | "127.0.0.1" | "[::1]"));
    ensure!(
        url.scheme() == "https" || local_http,
        "Jev endpoint must use HTTPS; HTTP is allowed only for loopback hosts"
    );
    ensure!(
        url.username().is_empty() && url.password().is_none(),
        "endpoint URL cannot contain credentials"
    );
    ensure!(
        url.query().is_none() && url.fragment().is_none(),
        "endpoint URL cannot contain a query or fragment"
    );
    Ok(())
}

fn bounded_response_body(response: &mut Response) -> std::result::Result<Vec<u8>, JevError> {
    let mut bytes = Vec::new();
    response
        .take(MAX_RESPONSE_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| JevError::Provider)?;
    if bytes.len() as u64 > MAX_RESPONSE_BYTES {
        return Err(JevError::Malformed);
    }
    Ok(bytes)
}

fn build_context(
    candidate: &Candidate,
    all_candidates: &[Candidate],
    sources: &HashMap<&str, &[u8]>,
) -> Result<CandidateContext> {
    let source = sources
        .get(candidate.path.as_str())
        .with_context(|| format!("source snapshot is missing {}", candidate.path))?;
    let mut parser = Parser::new();
    parser
        .set_language(&language_for(candidate.language))
        .with_context(|| format!("cannot initialize {} parser", candidate.language.label()))?;
    let tree = parser
        .parse(source, None)
        .with_context(|| format!("cannot parse {} for candidate context", candidate.path))?;
    let line_start = source
        .split(|byte| *byte == b'\n')
        .take(candidate.line.saturating_sub(1))
        .map(|line| line.len() + 1)
        .sum::<usize>();
    let candidate_byte = line_start.saturating_add(candidate.column.saturating_sub(1));
    ensure!(
        candidate_byte <= source.len(),
        "candidate position exceeds source file"
    );
    let node =
        locate_candidate(tree.root_node(), candidate_byte, candidate, source).context(format!(
            "cannot locate candidate syntax node {}:{}",
            candidate.path, candidate.line
        ))?;
    let full_excerpt = node.utf8_text(source).unwrap_or_default();
    let (excerpt, excerpt_truncated) = truncate_utf8(full_excerpt, MAX_EXCERPT_BYTES);
    let (enclosing, symbol) = enclosing_declaration(node, source);
    let (enclosing_source, enclosing_source_truncated) = enclosing
        .map(|declaration| {
            truncate_utf8(
                declaration.utf8_text(source).unwrap_or_default(),
                MAX_DECLARATION_BYTES,
            )
        })
        .map(|(text, truncated)| (Some(text), truncated))
        .unwrap_or((None, false));
    let start = node.start_position();
    let end = node.end_position();
    let mut related_sites = Vec::new();
    for other in all_candidates
        .iter()
        .filter(|other| other.fingerprint != candidate.fingerprint)
        .filter(|other| !other.inside_specification)
        .filter(|other| other.language == candidate.language && other.kind == candidate.kind)
        .take(8)
    {
        let (excerpt, excerpt_truncated) = truncate_utf8(&other.excerpt, MAX_RELATED_SITE_BYTES);
        related_sites.push(RelatedSite {
            fingerprint: other.fingerprint.clone(),
            language: other.language,
            path: other.path.clone(),
            symbol: None,
            construct_kind: other.kind.clone(),
            excerpt,
            excerpt_truncated,
        });
    }
    let context = CandidateContext {
        fingerprint: candidate.fingerprint.clone(),
        language: candidate.language,
        path: candidate.path.clone(),
        position: Position {
            start_line: start.row + 1,
            start_column: start.column + 1,
            end_line: end.row + 1,
            end_column: end.column + 1,
        },
        construct_kind: candidate.kind.clone(),
        excerpt,
        excerpt_truncated,
        enclosing_symbol: symbol,
        enclosing_source,
        enclosing_source_truncated,
        related_sites,
    };
    fit_context(context)
}

fn fit_context(mut context: CandidateContext) -> Result<CandidateContext> {
    loop {
        let encoded = serde_json::to_vec(&context)?;
        if encoded.len() <= MAX_CONTEXT_BYTES {
            return Ok(context);
        }
        let excess = encoded.len() - MAX_CONTEXT_BYTES;
        let mut reduced = false;
        for related in context.related_sites.iter_mut().rev() {
            if !related.excerpt.is_empty() {
                let target = related.excerpt.len().saturating_sub(excess.max(1));
                related.excerpt = truncate_utf8(&related.excerpt, target).0;
                related.excerpt_truncated = true;
                reduced = true;
                break;
            }
        }
        if !reduced
            && let Some(enclosing_source) = context.enclosing_source.as_mut()
            && !enclosing_source.is_empty()
        {
            let target = enclosing_source.len().saturating_sub(excess.max(1));
            *enclosing_source = truncate_utf8(enclosing_source, target).0;
            context.enclosing_source_truncated = true;
            reduced = true;
        }
        if !reduced && !context.excerpt.is_empty() {
            let target = context.excerpt.len().saturating_sub(excess.max(1));
            context.excerpt = truncate_utf8(&context.excerpt, target).0;
            context.excerpt_truncated = true;
            reduced = true;
        }
        if !reduced {
            bail!("candidate metadata alone exceeds the 24 KiB context limit");
        }
    }
}

fn language_for(language: Language) -> tree_sitter::Language {
    match language {
        Language::Python => tree_sitter_python::LANGUAGE.into(),
        Language::Swift => tree_sitter_swift::LANGUAGE.into(),
        Language::Rust => tree_sitter_rust::LANGUAGE.into(),
    }
}

fn locate_candidate<'tree>(
    node: Node<'tree>,
    byte: usize,
    candidate: &Candidate,
    source: &[u8],
) -> Option<Node<'tree>> {
    if byte < node.start_byte() || byte > node.end_byte() {
        return None;
    }
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        if let Some(found) = locate_candidate(child, byte, candidate, source) {
            return Some(found);
        }
    }
    let pos = node.start_position();
    let starts_at_candidate = pos.row + 1 == candidate.line && pos.column + 1 == candidate.column;
    (starts_at_candidate && candidate_node_matches(node, candidate, source)).then_some(node)
}

fn candidate_node_matches(node: Node<'_>, candidate: &Candidate, source: &[u8]) -> bool {
    match (candidate.language, candidate.kind.as_str(), node.kind()) {
        (Language::Python, "if", "if_statement")
        | (Language::Python, "conditional_expression", "conditional_expression")
        | (Language::Python, "comprehension_filter", "if_clause")
        | (Language::Python, "match", "match_statement")
        | (Language::Swift, "if", "if_statement" | "if_expression")
        | (Language::Swift, "guard", "guard_statement")
        | (Language::Swift, "switch", "switch_statement" | "switch_expression")
        | (Language::Rust, "if", "if_expression")
        | (Language::Rust, "match", "match_expression") => true,
        (Language::Swift, "defer", "call_expression") => node
            .utf8_text(source)
            .is_ok_and(|text| text.trim_start().starts_with("defer")),
        _ => false,
    }
}

fn enclosing_declaration<'tree>(
    node: Node<'tree>,
    source: &[u8],
) -> (Option<Node<'tree>>, Option<String>) {
    let mut parent = node.parent();
    while let Some(current) = parent {
        if is_declaration(current.kind()) {
            let name = current
                .child_by_field_name("name")
                .and_then(|child| child.utf8_text(source).ok())
                .map(str::to_owned);
            return (Some(current), name);
        }
        parent = current.parent();
    }
    (None, None)
}

fn is_declaration(kind: &str) -> bool {
    matches!(
        kind,
        "function_definition"
            | "function_item"
            | "function_declaration"
            | "class_definition"
            | "class_declaration"
            | "method_declaration"
            | "init_declaration"
            | "impl_item"
            | "struct_item"
            | "enum_item"
    )
}

fn truncate_utf8(text: &str, max_bytes: usize) -> (String, bool) {
    if text.len() <= max_bytes {
        return (text.to_owned(), false);
    }
    let mut end = max_bytes;
    while !text.is_char_boundary(end) {
        end -= 1;
    }
    (text[..end].to_owned(), true)
}

fn suggestion_from_response(
    candidate: &Candidate,
    context_digest: String,
    response: JevResponse,
    min_confidence: Option<f64>,
) -> Suggestion {
    let opportunity_answer = response.answers.get("opportunity");
    let concern_answer = response.answers.get("concern_kind");
    let opportunity_scores = opportunity_answer.and_then(valid_scores);
    let concern_scores = concern_answer.and_then(valid_scores);
    let valid = opportunity_answer.is_some_and(|answer| answer.answer_type == "choice")
        && concern_answer.is_some_and(|answer| answer.answer_type == "choice")
        && opportunity_scores.is_some()
        && concern_scores.is_some()
        && opportunity_answer.is_some_and(|answer| {
            parse_opportunity(&answer.choice).is_some()
                && answer.probabilities.contains_key(&answer.choice)
        })
        && concern_answer.is_some_and(|answer| {
            parse_concern(&answer.choice).is_some()
                && answer.probabilities.contains_key(&answer.choice)
        })
        && !response.model.trim().is_empty();
    let opportunity_below_threshold = min_confidence.is_some_and(|threshold| {
        opportunity_answer.is_some_and(|answer| answer.confidence < threshold)
    });
    let concern_below_threshold = min_confidence.is_some_and(|threshold| {
        concern_answer.is_some_and(|answer| answer.confidence < threshold)
    });
    let threshold_breached = opportunity_below_threshold || concern_below_threshold;
    let mut diagnostics = Vec::new();
    if !valid {
        diagnostics.push(Diagnostic::MalformedProviderOutput);
    }
    if threshold_breached {
        diagnostics.push(Diagnostic::CloseDecision);
    }
    let opportunity = if !valid || opportunity_below_threshold {
        Opportunity::NeedsReview
    } else {
        parse_opportunity(&opportunity_answer.expect("validated above").choice).unwrap()
    };
    let concern_kind = if !valid || concern_below_threshold {
        ConcernKind::Unknown
    } else {
        parse_concern(&concern_answer.expect("validated above").choice).unwrap()
    };
    let scores = ProviderScores {
        opportunity: opportunity_scores,
        concern_kind: concern_scores,
    };
    let semantics = ScoreSemantics {
        opportunity: scores.opportunity.as_ref().map(|_| SCORE_SEMANTICS),
        concern_kind: scores.concern_kind.as_ref().map(|_| SCORE_SEMANTICS),
    };
    Suggestion {
        candidate_fingerprint: candidate.fingerprint.clone(),
        context_digest,
        model_id: Some(response.model),
        model_revision: None,
        cacheable: false,
        opportunity,
        concern_kind,
        diagnostics,
        opportunity_rationale: unavailable_rationale(),
        concern_rationale: unavailable_rationale(),
        provider_scores: scores,
        score_semantics: semantics,
    }
}

const SCORE_SEMANTICS: &str =
    "Provider-reported Choice probabilities and confidence; not calibrated across models.";

fn valid_scores(answer: &JevAnswer) -> Option<ChoiceScores> {
    if answer.answer_type != "choice"
        || !answer.confidence.is_finite()
        || !(0.0..=1.0).contains(&answer.confidence)
        || answer.probabilities.is_empty()
        || answer
            .probabilities
            .values()
            .any(|value| !value.is_finite() || !(0.0..=1.0).contains(value))
    {
        return None;
    }
    Some(ChoiceScores {
        probabilities: answer.probabilities.clone(),
        confidence: Some(answer.confidence),
    })
}

fn fallback_suggestion(
    candidate: &Candidate,
    context_digest: String,
    diagnostic: Diagnostic,
) -> Suggestion {
    Suggestion {
        candidate_fingerprint: candidate.fingerprint.clone(),
        context_digest,
        model_id: None,
        model_revision: None,
        cacheable: false,
        opportunity: Opportunity::NeedsReview,
        concern_kind: ConcernKind::Unknown,
        diagnostics: vec![diagnostic],
        opportunity_rationale: unavailable_rationale(),
        concern_rationale: unavailable_rationale(),
        provider_scores: ProviderScores {
            opportunity: None,
            concern_kind: None,
        },
        score_semantics: ScoreSemantics {
            opportunity: None,
            concern_kind: None,
        },
    }
}

fn unavailable_rationale() -> Rationale {
    Rationale {
        text: None,
        source: "unavailable",
    }
}

fn parse_opportunity(value: &str) -> Option<Opportunity> {
    match value {
        "eligible" => Some(Opportunity::Eligible),
        "excluded" => Some(Opportunity::Excluded),
        "needs_review" => Some(Opportunity::NeedsReview),
        _ => None,
    }
}

fn parse_concern(value: &str) -> Option<ConcernKind> {
    match value {
        "policy" => Some(ConcernKind::Policy),
        "mechanics" => Some(ConcernKind::Mechanics),
        "variant_behavior" => Some(ConcernKind::VariantBehavior),
        "unknown" => Some(ConcernKind::Unknown),
        _ => None,
    }
}

fn rubric() -> Rubric {
    Rubric {
        id: "specification_metrics.candidate.v1",
        version: 1,
        opportunity_definitions: opportunity_definitions(),
        concern_kind_definitions: concern_definitions(),
    }
}

fn opportunity_definitions() -> BTreeMap<&'static str, &'static str> {
    BTreeMap::from([
        (
            "eligible",
            "Stable domain decision or policy suitable for a named, reusable Specification, including repeated decisions or variant dispatch.",
        ),
        (
            "excluded",
            "Technical mechanics or a local construct outside the intended Specification opportunity definition, including a rule already owned by a Specification.",
        ),
        (
            "needs_review",
            "Evidence is ambiguous, insufficient, unsupported, or cannot be classified reliably. This is unknown, not an exclusion.",
        ),
    ])
}

fn concern_definitions() -> BTreeMap<&'static str, &'static str> {
    BTreeMap::from([
        (
            "policy",
            "Durable product rule, authority, trust, evidence, eligibility, or lifecycle decision.",
        ),
        (
            "mechanics",
            "Parsing, representation, I/O, adaptation, or technical enforcement.",
        ),
        (
            "variant_behavior",
            "Dispatches behavior over domain variants such as an enum, type, or platform.",
        ),
        (
            "unknown",
            "Available evidence does not support a reliable concern-kind classification.",
        ),
    ])
}

fn choice_questions() -> Value {
    json!({
        "opportunity": {
            "type": "choice",
            "instructions": format!("{PROMPT_CONTRACT} Classify opportunity only."),
            "criteria": opportunity_definitions()
        },
        "concern_kind": {
            "type": "choice",
            "instructions": format!("{PROMPT_CONTRACT} Classify concern_kind only."),
            "criteria": concern_definitions()
        }
    })
}

fn digest(algorithm: &str, bytes: &[u8]) -> String {
    format!("{algorithm}:{}", blake3::hash(bytes).to_hex())
}

fn git_revision(root: &Path) -> Option<String> {
    let directory = if root.is_file() { root.parent()? } else { root };
    let output = Command::new("git")
        .arg("-C")
        .arg(directory)
        .args(["rev-parse", "HEAD"])
        .output()
        .ok()?;
    output
        .status
        .success()
        .then(|| String::from_utf8_lossy(&output.stdout).trim().to_owned())
}

fn make_run_id(timestamp: &str, source_digest: &str, profile_digest: &str) -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let seed = format!("{timestamp}:{source_digest}:{profile_digest}:{nanos}");
    let hash = blake3::hash(seed.as_bytes()).to_hex().to_string();
    format!("run-{}-{}", nanos, &hash[..12])
}

#[cfg(test)]
mod tests {
    use super::*;

    fn context() -> CandidateContext {
        CandidateContext {
            fingerprint: "blake3:candidate".to_owned(),
            language: Language::Python,
            path: "src/example.py".to_owned(),
            position: Position {
                start_line: 1,
                start_column: 1,
                end_line: 1,
                end_column: 2,
            },
            construct_kind: "if_statement".to_owned(),
            excerpt: "x".repeat(MAX_EXCERPT_BYTES),
            excerpt_truncated: false,
            enclosing_symbol: Some("example".to_owned()),
            enclosing_source: Some("y".repeat(MAX_DECLARATION_BYTES)),
            enclosing_source_truncated: false,
            related_sites: (0..8)
                .map(|index| RelatedSite {
                    fingerprint: format!("blake3:related-{index}"),
                    language: Language::Python,
                    path: format!("src/related-{index}.py"),
                    symbol: None,
                    construct_kind: "if_statement".to_owned(),
                    excerpt: "z".repeat(MAX_RELATED_SITE_BYTES),
                    excerpt_truncated: false,
                })
                .collect(),
        }
    }

    #[test]
    fn aggregate_context_limit_trims_excerpts_and_marks_them() {
        let fitted = fit_context(context()).expect("context should fit after excerpt trimming");
        assert!(serde_json::to_vec(&fitted).unwrap().len() <= MAX_CONTEXT_BYTES);
        assert!(
            fitted
                .related_sites
                .iter()
                .any(|site| site.excerpt_truncated)
        );
    }

    #[test]
    fn context_fails_if_non_excerpt_metadata_exceeds_limit() {
        let mut context = context();
        context.path = "p".repeat(MAX_CONTEXT_BYTES + 1);
        assert!(fit_context(context).is_err());
    }

    #[test]
    fn invalid_json_is_reported_as_malformed_provider_output() {
        assert!(matches!(
            parse_response_body(b"{"),
            Err(JevError::Malformed)
        ));
    }
}
