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
