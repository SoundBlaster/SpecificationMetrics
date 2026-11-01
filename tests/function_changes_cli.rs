use std::{fs, process::Command};

use serde_json::{Value, json};
use tempfile::tempdir;

fn compare(old: Value, new: Value) -> (Value, String) {
    let dir = tempdir().unwrap();
    fs::write(dir.path().join("a.py"), "if ready: pass\n").unwrap();
    let config = dir.path().join("config.toml");
    fs::write(
        &config,
        "schema_version=1\nproject='test'\nroot='.'\nincludes=['a.py']\n",
    )
    .unwrap();
    let run = |args: &[&str]| {
        let out = Command::new(env!("CARGO_BIN_EXE_specification-metrics"))
            .args(args)
            .output()
            .unwrap();
        assert!(
            out.status.success(),
            "{}",
            String::from_utf8_lossy(&out.stderr)
        );
        out.stdout
    };
    let original = run(&["collect", "--config", config.to_str().unwrap()]);
    let mut snapshot: Value = serde_json::from_slice(&original).unwrap();
    snapshot["primary"]["provisional"] = false.into();
    snapshot["status"] = "complete".into();
    let b = dir.path().join("before.json");
    let a = dir.path().join("after.json");
    for (path, extra) in [(&b, old), (&a, new)] {
        snapshot["supplementary"] = json!({"python_complexity":extra});
        fs::write(path, serde_json::to_vec(&snapshot).unwrap()).unwrap();
    }
    let args = ["compare", b.to_str().unwrap(), a.to_str().unwrap()];
    let report: Value = serde_json::from_slice(&run(&args)).unwrap();
    let mut args = args.to_vec();
    args.extend(["--github-markdown", "org/repo"]);
    let md = String::from_utf8(run(&args)).unwrap();
    let details_count = usize::from(report["function_changes"]["status"] != "not_requested");
    assert_eq!(md.matches("<details>").count(), details_count);
    assert_eq!(md.matches("</details>").count(), details_count);
    if details_count != 0 {
        assert!(md.contains("<summary>Python function complexity hotspots · "));
        assert!(md.contains("</summary>\n\nComparison"));
        assert!(md.ends_with("\n\n</details>\n"));
        assert!(!md.contains("<details open"));
    }
    (report, md)
}

fn metrics(files: Value) -> Value {
    json!({"status":"complete", "versions":{"radon":"6.0.1","complexipy":"8.0.1"},
           "files": files, "summary":{"cog_max":552}})
}

fn file(rows: Value) -> Value {
    json!({"cognitive":rows, "cyclomatic":[]})
}

#[test]
fn unchanged_global_max_does_not_hide_new_hotspot_and_moves_do_not_invent_growth() {
    let stable = file(json!([{"name":"legacy", "line":1,"cog":552}]));
    let (report, md) = compare(
        metrics(json!({"stable.py":stable,"old.py":file(json!([
            {"name":"check_packages","line":3,"cog":77},
            {"name":"changed","line":10,"cog":9},
            {"name":"shifted","line":30,"cog":4}
        ]))})),
        metrics(json!({"stable.py":stable,"new.py":file(json!([
            {"name":"check_packages","line":52,"cog":77}
        ])),"old.py":file(json!([
            {"name":"changed","line":20,"cog":12},
            {"name":"shifted","line":40,"cog":4}
        ]))})),
    );
    let changes = &report["function_changes"];
    assert_eq!(changes["status"], "complete");
    let rows = changes["rows"].as_array().unwrap();
    assert_eq!(rows.len(), 3); // two unmatched move candidates and one changed score
    assert!(rows.iter().take(2).all(|r| r["delta"].is_null()));
    assert!(
        rows.iter()
            .take(2)
            .all(|r| r["correspondence"] == "counterpart_not_established")
    );
    assert_eq!(rows[2]["delta"], 3);
    assert!(md.contains("check_packages"));
    assert!(md.contains("not established"));
    assert!(!md.contains("shifted"));
    assert!(!md.contains("legacy"));
    assert_eq!(
        report["supplementary"]["python_complexity"]["delta"]["cog_max"],
        0.0
    );
}

#[test]
fn duplicate_method_names_and_renames_are_not_paired_by_line_or_order() {
    let functions = |rows| json!({"rules.py":{"cyclomatic":rows,"cognitive":[]}});
    let (report, _) = compare(
        metrics(functions(json!([
            {"name":"accepts","line":2,"cc":2},
            {"name":"accepts","line":8,"cc":4},
            {"name":"old_name","line":12,"cc":10}
        ]))),
        metrics(functions(json!([
            {"name":"accepts","line":2,"cc":9},
            {"name":"new_name","line":12,"cc":10}
        ]))),
    );
    let rows = report["function_changes"]["rows"].as_array().unwrap();
    assert_eq!(rows.len(), 5);
    assert!(rows.iter().all(|r| r["delta"].is_null()));
    assert_eq!(
        rows.iter()
            .filter(|r| r["correspondence"] == "duplicate_reported_name")
            .count(),
        3
    );
}

#[test]
fn missing_failed_malformed_and_incompatible_details_are_not_empty_successes() {
    let valid = metrics(json!({"a.py":file(json!([]))}));
    for (bad, status) in [
        (json!({"status":"failed"}), "not_comparable"),
        (
            json!({"status":"complete","versions":{"radon":"other","complexipy":"8.0.1"},"files":{}}),
            "not_comparable",
        ),
        (metrics(Value::Null), "unavailable"),
        (
            metrics(json!({"a.py":{"cognitive":[],"cyclomatic":[{"name":"f","line":0,"cc":1}]}})),
            "unavailable",
        ),
    ] {
        let (report, md) = compare(valid.clone(), bad);
        assert_eq!(report["function_changes"]["status"], status);
        assert!(
            report["function_changes"]["rows"]
                .as_array()
                .unwrap()
                .is_empty()
        );
        assert!(md.contains("Function details unavailable"));
    }
    let (report, md) = compare(
        json!({"status":"not_requested"}),
        json!({"status":"not_requested"}),
    );
    assert_eq!(report["function_changes"]["status"], "not_requested");
    assert!(!md.contains("Python function complexity hotspots"));
}

#[test]
fn unchanged_duplicate_score_multisets_do_not_swamp_hotspots() {
    let group = |line| {
        file(json!([
            {"name":"accepts","line":line,"cog":200},
            {"name":"accepts","line":line+10,"cog":300}
        ]))
    };
    let (report, md) = compare(
        metrics(json!({"stable.py":group(1)})),
        metrics(json!({"stable.py":group(21),"new.py":file(json!([
            {"name":"hotspot","line":1,"cog":77}
        ]))})),
    );
    assert_eq!(
        report["function_changes"]["rows"].as_array().unwrap().len(),
        1
    );
    assert!(md.contains("hotspot"));
    assert!(!md.contains("accepts"));
}

#[test]
fn oversized_names_do_not_bypass_markdown_byte_budget() {
    let (report, md) = compare(
        metrics(json!({})),
        metrics(json!({"a.py":file(json!([
            {"name":"x".repeat(13000),"line":1,"cog":77}
        ]))})),
    );
    assert_eq!(
        report["function_changes"]["rows"].as_array().unwrap().len(),
        1
    );
    assert!(md.len() < 2000);
    assert!(md.contains("More function observations"));
}

#[test]
fn markdown_is_bounded_escaped_and_keeps_full_json() {
    let rows: Vec<_> = (0..12)
        .map(|i| json!({"name":format!("f|`{i}"),"line":i+1,"cog":i+10}))
        .collect();
    let (report, md) = compare(
        metrics(json!({})),
        metrics(json!({"a|`[x].py":file(json!(rows))})),
    );
    assert_eq!(
        report["function_changes"]["rows"].as_array().unwrap().len(),
        12
    );
    assert_eq!(md.lines().filter(|s| s.starts_with("| Cog |")).count(), 5);
    assert!(md.contains("More function observations"));
    assert!(md.contains("a%7C%60%5Bx%5D.py"));
    assert!(!md.contains("f|`"));
    assert_eq!(report["function_changes"]["rows"][0]["after"]["value"], 21);
}
