use super::*;
use std::process::Command;

const RULE: &str = "from specification_core import PredicateSpec\nALLOCATION = PredicateSpec(lambda context: context.workspace == context.requested_workspace and context.commit == context.requested_commit and context.authorized is True, name='allocation')\n";
const PREDICATE: &str = "allocation['workspace_identity'] == request.workspace_identity and allocation['expected_commit'] == request.expected_commit and allocation['authorized'] is True";

fn git(root: &Path, args: &[&str]) -> String {
    let out = Command::new("git")
        .arg("-C")
        .arg(root)
        .args(args)
        .output()
        .unwrap();
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    String::from_utf8(out.stdout).unwrap().trim().into()
}

fn commit(root: &Path) -> String {
    git(root, &["add", "."]);
    git(
        root,
        &[
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "fixture",
        ],
    );
    git(root, &["rev-parse", "HEAD"])
}

fn fixture(source: &str) -> (tempfile::TempDir, String, std::path::PathBuf) {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path();
    git(root, &["init", "-q"]);
    fs::create_dir(root.join("tools")).unwrap();
    fs::write(root.join("tools/spec.py"), RULE).unwrap();
    fs::write(root.join("tools/caller.py"), source).unwrap();
    let base = commit(root);
    let tree = ast::parse(RULE).unwrap();
    let node = ast::declaration(&tree, RULE, "ALLOCATION").unwrap();
    let catalog = dir.path().join("catalog.toml");
    fs::write(
        &catalog,
        format!(
            r#"schema_version=1
project="fixture"
[[rules]]
id="allocation"
bounded_context="publication"
paths=["tools"]
canonical_path="tools/spec.py"
canonical_symbol="ALLOCATION"
canonical_digest="{}"
[[rules.templates]]
id="historical"
expression="{}"
renameable_identifiers=["allocation","request"]
source_url="https://github.com/example/project/commit/123"
"#,
            digest(ast::text(node, RULE)),
            PREDICATE
        ),
    )
    .unwrap();
    (dir, base, catalog)
}

#[test]
fn exact_guard_is_new_and_canonical_rule_is_not_a_clone() {
    let (dir, base, catalog) = fixture("pass\n");
    fs::write(
        dir.path().join("tools/caller.py"),
        format!("require({PREDICATE}, 'binding mismatch')\n"),
    )
    .unwrap();
    commit(dir.path());
    let report = check(dir.path(), &catalog, &base, "HEAD", None).unwrap();
    assert_eq!(report.new_reimplementations, 1);
    assert_eq!(report.after_reimplementations, 1);
    assert_eq!(report.new_near_matches, 0);
}

#[test]
fn local_binder_renaming_and_quote_style_preserve_match() {
    let (dir, base, catalog) = fixture("pass\n");
    let predicate = PREDICATE
        .replace("allocation[", "facts[")
        .replace("request.", "target.")
        .replace('\'', "\"");
    fs::write(
        dir.path().join("tools/caller.py"),
        format!("if ({predicate}):\n    publish()\n"),
    )
    .unwrap();
    commit(dir.path());
    assert_eq!(
        check(dir.path(), &catalog, &base, "HEAD", None)
            .unwrap()
            .new_reimplementations,
        1
    );
}

#[test]
fn existing_inline_baseline_and_line_shifts_do_not_block() {
    let (dir, base, catalog) = fixture(&format!("require({PREDICATE}, 'mismatch')\n"));
    fs::write(
        dir.path().join("tools/caller.py"),
        format!("# new comment\nrequire({PREDICATE}, 'mismatch')\n"),
    )
    .unwrap();
    commit(dir.path());
    let report = check(dir.path(), &catalog, &base, "HEAD", None).unwrap();
    assert_eq!(report.before_reimplementations, 1);
    assert_eq!(report.new_reimplementations, 0);
}

#[test]
fn reordered_conditions_and_changed_literals_are_review_only() {
    let (dir, base, catalog) = fixture("pass\n");
    let parts: Vec<_> = PREDICATE.split(" and ").collect();
    let reordered = format!("{} and {} and {}", parts[2], parts[1], parts[0]);
    fs::write(
        dir.path().join("tools/caller.py"),
        format!(
            "require({reordered}, 'mismatch')\nrequire({}, 'different rule')\n",
            PREDICATE.replace("is True", "is False")
        ),
    )
    .unwrap();
    commit(dir.path());
    let report = check(dir.path(), &catalog, &base, "HEAD", None).unwrap();
    assert_eq!(report.new_reimplementations, 0);
    assert_eq!(report.new_near_matches, 2);
    assert_eq!(report.semantic_review_requests.len(), 2);
}

fn add_review_template(catalog: &Path, id: &str, expression: &str) {
    let original = fs::read_to_string(catalog).unwrap();
    fs::write(catalog, format!("{original}\n[[rules.review_templates]]\nid='{id}'\nexpression=\"\"\"{expression}\"\"\"\nrenameable_identifiers=['allocation','request']\nsource_url='https://github.com/example/project/commit/123'\n")).unwrap();
}

#[test]
fn partial_template_is_opt_in_review_only_and_has_provenance() {
    let partial = PREDICATE.split(" and ").next().unwrap();
    let (dir, base, catalog) = fixture("pass\n");
    fs::write(
        dir.path().join("tools/caller.py"),
        format!("if {partial}:\n    publish()\n"),
    )
    .unwrap();
    commit(dir.path());
    assert!(
        check(dir.path(), &catalog, &base, "HEAD", None)
            .unwrap()
            .findings
            .is_empty()
    );
    add_review_template(&catalog, "partial", partial);
    let report = check(dir.path(), &catalog, &base, "HEAD", None).unwrap();
    assert_eq!(report.new_reimplementations, 0);
    assert_eq!(report.new_near_matches, 1);
    assert_eq!(report.after_reimplementations, 0);
    assert_eq!(
        report.findings[0].match_basis.as_deref(),
        Some("review_template")
    );
    assert_eq!(report.findings[0].template_id.as_deref(), Some("partial"));
    let request = &report.semantic_review_requests[0]["state"];
    assert_eq!(request["review_template"]["expression"], partial);
    assert_eq!(
        request["review_template"]["source_url"],
        "https://github.com/example/project/commit/123"
    );
}

#[test]
fn exact_policy_cannot_be_downgraded_by_review_template() {
    let (dir, base, catalog) = fixture("pass\n");
    add_review_template(&catalog, "also-review", PREDICATE);
    fs::write(
        dir.path().join("tools/caller.py"),
        format!("if {PREDICATE}:\n    publish()\n"),
    )
    .unwrap();
    commit(dir.path());
    let report = check(dir.path(), &catalog, &base, "HEAD", None).unwrap();
    assert_eq!(report.new_reimplementations, 1);
    assert_eq!(report.new_near_matches, 0);
    assert_eq!(
        report.findings[0].match_basis.as_deref(),
        Some("equivalent_template")
    );
}

#[test]
fn review_template_baseline_survives_binder_renaming_and_line_shifts() {
    let partial = PREDICATE.split(" and ").next().unwrap();
    let (dir, base, catalog) = fixture(&format!("if {partial}:\n    publish()\n"));
    add_review_template(&catalog, "partial", partial);
    fs::write(
        dir.path().join("tools/caller.py"),
        format!(
            "# new line\nif {}:\n    publish()\n",
            partial
                .replace("allocation", "facts")
                .replace("request", "target")
        ),
    )
    .unwrap();
    commit(dir.path());
    let report = check(dir.path(), &catalog, &base, "HEAD", None).unwrap();
    assert_eq!(report.new_near_matches, 0);
    assert_eq!(report.findings.len(), 1);
    assert!(!report.findings[0].introduced);
}

#[test]
fn unrelated_equality_and_wrong_fields_do_not_match_review_template() {
    let (dir, base, catalog) = fixture("pass\n");
    add_review_template(
        &catalog,
        "partial",
        PREDICATE.split(" and ").next().unwrap(),
    );
    fs::write(dir.path().join("tools/caller.py"), "if downloaded_sha == cached_sha:\n    pass\nif allocation['title'] == request.title:\n    pass\n").unwrap();
    commit(dir.path());
    assert!(
        check(dir.path(), &catalog, &base, "HEAD", None)
            .unwrap()
            .findings
            .is_empty()
    );
}

#[test]
fn review_templates_do_not_expand_feature_overlap_heuristic() {
    let (dir, base, catalog) = fixture("pass\n");
    let partial = "draft['title'] == document['title'] and draft['status'] == document['status'] and draft['owner'] == document['owner']";
    add_review_template(&catalog, "partial", partial);
    fs::write(
        dir.path().join("tools/caller.py"),
        format!("if {}:\n    publish()\n", partial.replacen("==", "!=", 1)),
    )
    .unwrap();
    commit(dir.path());
    assert!(
        check(dir.path(), &catalog, &base, "HEAD", None)
            .unwrap()
            .findings
            .is_empty()
    );
}

#[test]
fn review_templates_reject_duplicate_ids_and_invalid_expressions() {
    let (dir, base, catalog) = fixture("pass\n");
    let original = fs::read_to_string(&catalog).unwrap();
    add_review_template(&catalog, "historical", "allocation is request");
    assert!(check(dir.path(), &catalog, &base, "HEAD", None).is_err());
    fs::write(&catalog, original).unwrap();
    add_review_template(&catalog, "broken", "allocation ==");
    assert!(check(dir.path(), &catalog, &base, "HEAD", None).is_err());
}

#[test]
fn proper_spec_call_and_context_preparation_are_not_copies() {
    let (dir, base, catalog) = fixture("pass\n");
    fs::write(dir.path().join("tools/caller.py"),"from spec import ALLOCATION\ncontext = Context(workspace=facts['workspace_identity'], commit=facts['expected_commit'], authorized=facts['authorized'])\nrequire(ALLOCATION.is_satisfied_by(context), 'mismatch')\n").unwrap();
    commit(dir.path());
    let report = check(dir.path(), &catalog, &base, "HEAD", None).unwrap();
    assert_eq!(report.new_reimplementations, 0);
    assert_eq!(report.new_near_matches, 0);
    assert_eq!(report.reused_specifications, 1);
}

#[test]
fn owner_changes_and_parse_failures_cannot_silently_pass() {
    let (dir, base, catalog) = fixture("pass\n");
    fs::write(
        dir.path().join("tools/spec.py"),
        RULE.replace("is True", "is False"),
    )
    .unwrap();
    commit(dir.path());
    assert!(check(dir.path(), &catalog, &base, "HEAD", None).is_err());
    fs::write(dir.path().join("tools/spec.py"), RULE).unwrap();
    fs::write(dir.path().join("tools/caller.py"), "if broken(\n").unwrap();
    commit(dir.path());
    let report = check(dir.path(), &catalog, &base, "HEAD", None).unwrap();
    assert_eq!(report.status, "incomplete");
}

#[test]
fn scoped_test_sources_are_ignored_and_snapshots_are_idempotent() {
    let (dir, base, catalog) = fixture("pass\n");
    fs::create_dir(dir.path().join("tests")).unwrap();
    fs::write(
        dir.path().join("tests/example.py"),
        format!("require({PREDICATE}, 'mismatch')\n"),
    )
    .unwrap();
    commit(dir.path());
    let report = check(dir.path(), &catalog, &base, "HEAD", None).unwrap();
    assert_eq!(report.files_checked, 0);
    let store = dir.path().join("metrics.sqlite");
    let first = save(&store, &report).unwrap();
    assert_eq!(save(&store, &report).unwrap(), first);
    assert_eq!(history(&store, 10).unwrap().as_array().unwrap().len(), 1);
}

#[test]
fn exact_renames_do_not_introduce_new_reimplementations() {
    let (dir, base, catalog) = fixture(&format!("require({PREDICATE}, 'mismatch')\n"));
    git(dir.path(), &["mv", "tools/caller.py", "tools/moved.py"]);
    commit(dir.path());
    assert_eq!(
        check(dir.path(), &catalog, &base, "HEAD", None)
            .unwrap()
            .new_reimplementations,
        0
    );
}

#[test]
fn aliased_spec_import_is_reuse_but_compound_predicate_is_not_exempt() {
    let (dir, base, catalog) = fixture("pass\n");
    fs::write(dir.path().join("tools/caller.py"),format!("from spec import ALLOCATION as policy, Other\nrequire(policy.is_satisfied_by(context), 'ok')\nrequire(policy.is_satisfied_by(context) and ({PREDICATE}), 'copy')\n")).unwrap();
    commit(dir.path());
    let report = check(dir.path(), &catalog, &base, "HEAD", None).unwrap();
    assert_eq!(report.reused_specifications, 1);
    assert_eq!(report.new_near_matches, 1);
}

#[test]
fn canonical_binder_is_derived_and_only_its_declaration_is_excluded() {
    let (dir, base, catalog) = fixture("pass\n");
    let changed = RULE.replace("context", "facts");
    fs::write(dir.path().join("tools/spec.py"), &changed).unwrap();
    let catalog_body = fs::read_to_string(&catalog).unwrap();
    let tree = ast::parse(&changed).unwrap();
    let node = ast::declaration(&tree, &changed, "ALLOCATION").unwrap();
    fs::write(
        &catalog,
        catalog_body.replace(
            &digest(ast::text(
                ast::declaration(&ast::parse(RULE).unwrap(), RULE, "ALLOCATION").unwrap(),
                RULE,
            )),
            &digest(ast::text(node, &changed)),
        ),
    )
    .unwrap();
    fs::write(dir.path().join("tools/caller.py"),"if other.workspace == other.requested_workspace and other.commit == other.requested_commit and other.authorized is True:\n    pass\n").unwrap();
    commit(dir.path());
    let report = check(dir.path(), &catalog, &base, "HEAD", None).unwrap();
    assert_eq!(report.new_reimplementations, 1);
    assert_eq!(report.findings[0].template_id.as_deref(), Some("canonical"));
}

#[test]
fn rename_out_of_scope_preserves_before_count_and_copy_into_scope_is_new() {
    let (dir, base, catalog) = fixture(&format!("require({PREDICATE}, 'old')\n"));
    fs::create_dir(dir.path().join("other")).unwrap();
    git(dir.path(), &["mv", "tools/caller.py", "other/caller.py"]);
    commit(dir.path());
    let report = check(dir.path(), &catalog, &base, "HEAD", None).unwrap();
    assert_eq!(report.before_reimplementations, 1);
    assert_eq!(report.after_reimplementations, 0);
    let base = git(dir.path(), &["rev-parse", "HEAD"]);
    fs::copy(
        dir.path().join("other/caller.py"),
        dir.path().join("tools/new.py"),
    )
    .unwrap();
    commit(dir.path());
    assert_eq!(
        check(dir.path(), &catalog, &base, "HEAD", None)
            .unwrap()
            .new_reimplementations,
        1
    );
}

#[test]
fn jev_suggestions_preserve_provenance_and_never_block_near_matches() {
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::time::Duration;
    for (status,body,expected,diagnostic) in [
        ("200 OK",json!({"model":"fixture-model","answers":{"rule_reuse":{"type":"choice","choice":"same_rule","confidence":0.9,"probabilities":{"same_rule":0.9,"different_rule":0.05,"needs_review":0.05}}}}).to_string(),"same_rule", None),
        ("200 OK","{}".into(),"needs_review", Some("malformed_provider_output")),
        ("200 OK","{".into(),"needs_review", Some("malformed_provider_output")),
        ("200 OK","x".repeat(1024 * 1024 + 1),"needs_review", Some("malformed_provider_output")),
        ("503 Service Unavailable","provider diagnostic must not leak".into(),"needs_review", Some("provider_error")),
    ] {
        let listener=TcpListener::bind("127.0.0.1:0").unwrap();
        let endpoint=format!("http://{}/typesafe",listener.local_addr().unwrap());
        let server=std::thread::spawn(move || {
            let (mut socket,_)=listener.accept().unwrap();
            socket.set_read_timeout(Some(Duration::from_secs(5))).unwrap();
            let mut request=vec![];let mut buf=[0u8;4096];
            loop {
                let size=socket.read(&mut buf).unwrap(); assert!(size>0);request.extend_from_slice(&buf[..size]);
                if let Some(end)=request.windows(4).position(|v|v==b"\r\n\r\n") {
                    let header=String::from_utf8_lossy(&request[..end]);
                    let len=header.lines().find_map(|l|l.to_lowercase().strip_prefix("content-length: ").and_then(|v|v.parse::<usize>().ok())).unwrap();
                    if request.len()>=end+4+len {
                        let value:Value=serde_json::from_slice(&request[end+4..end+4+len]).unwrap();
                        assert!(value["state"]["existing_rule"]["definition"].is_string());
                        assert_eq!(value["questions"]["rule_reuse"]["type"],"choice");break;
                    }
                }
            }
            write!(socket,"HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",body.len()).unwrap();
            // Oversized responses are rejected before all bytes are consumed.
            let _ = socket.write_all(body.as_bytes());
        });
        let (dir,base,catalog)=fixture("pass\n");
        fs::write(dir.path().join("tools/caller.py"),format!("require({}, 'changed')\n",PREDICATE.replace("is True","is False"))).unwrap();
        commit(dir.path());
        let client=JevClient::new(&endpoint,"requested-model","fixture-secret".into(),Duration::from_secs(5)).unwrap();
        let report=check(dir.path(),&catalog,&base,"HEAD",Some(&client)).unwrap();server.join().unwrap();
        assert_eq!(report.new_reimplementations,0);
        let suggestion=report.findings[0].semantic_suggestion.as_ref().unwrap();
        assert_eq!(suggestion["choice"],expected);
        if let Some(diagnostic) = diagnostic {
            assert_eq!(suggestion["diagnostic"], diagnostic);
        }
        assert_eq!(suggestion["requested_model"],"requested-model");
        assert!(suggestion["input_digest"].as_str().unwrap().starts_with("blake3:"));
        let output=serde_json::to_string(&report).unwrap();
        assert!(!output.contains("fixture-secret"));assert!(!output.contains("provider diagnostic"));
    }
}
