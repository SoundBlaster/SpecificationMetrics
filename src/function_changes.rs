//! Metric-change hotspots; reported names are structural keys, not semantic identity.
use std::collections::{BTreeMap, BTreeSet};

use serde::Serialize;
use serde_json::Value;

use crate::collection::Collection;

#[derive(Clone, Debug, Serialize)]
pub struct Site {
    path: String,
    name: String,
    line: u64,
    value: i64,
}

#[derive(Debug, Serialize)]
pub struct Row {
    metric: &'static str,
    before: Option<Site>,
    after: Option<Site>,
    delta: Option<i64>,
    correspondence: &'static str,
}

#[derive(Debug, Serialize)]
pub struct Changes {
    version: u32,
    status: &'static str,
    reason: Option<&'static str>,
    rows: Vec<Row>,
}

type Index = BTreeMap<(String, String), Vec<Site>>;

fn index(value: &Value, field: &str, metric: &str) -> Option<Index> {
    let mut out = Index::new();
    for (path, file) in value["files"].as_object()? {
        if path.is_empty() {
            return None;
        }
        for row in file[field].as_array()? {
            let name = row["name"].as_str()?.to_owned();
            let line = row["line"].as_u64()?;
            let value = row[metric].as_i64()?;
            if name.is_empty() || line == 0 || value < 0 {
                return None;
            }
            out.entry((path.clone(), name.clone()))
                .or_default()
                .push(Site {
                    path: path.clone(),
                    name,
                    line,
                    value,
                });
        }
    }
    Some(out)
}

pub fn compare(before: &Collection, after: &Collection) -> Changes {
    let mut result = Changes {
        version: 1,
        status: "complete",
        reason: None,
        rows: Vec::new(),
    };
    let b = &before.supplementary["python_complexity"];
    let a = &after.supplementary["python_complexity"];
    if [before, after].iter().all(|c| {
        c.supplementary["python_complexity"]["status"] == "not_requested"
            || (c.supplementary["python_complexity"].is_null()
                && c.supplementary["status"] == "not_requested")
    }) {
        result.status = "not_requested";
        return result;
    }
    if b["status"] != "complete"
        || a["status"] != "complete"
        || b["versions"] != a["versions"]
        || ["radon", "complexipy"]
            .iter()
            .any(|tool| !b["versions"][tool].as_str().is_some_and(|s| !s.is_empty()))
    {
        result.status = "not_comparable";
        result.reason = Some("incomplete_or_different_tools");
        return result;
    }
    for (field, metric, label) in [("cognitive", "cog", "Cog"), ("cyclomatic", "cc", "CC")] {
        let (Some(b), Some(a)) = (index(b, field, metric), index(a, field, metric)) else {
            result.status = "unavailable";
            result.reason = Some("missing_or_invalid_function_details");
            result.rows.clear();
            return result;
        };
        let keys: BTreeSet<_> = b.keys().chain(a.keys()).collect();
        for key in keys {
            let old = b.get(key).map(Vec::as_slice).unwrap_or_default();
            let new = a.get(key).map(Vec::as_slice).unwrap_or_default();
            if let ([old], [new]) = (old, new) {
                if old.value != new.value {
                    result.rows.push(Row {
                        metric: label,
                        before: Some(old.clone()),
                        after: Some(new.clone()),
                        delta: Some(new.value - old.value),
                        correspondence: "same_path_and_unique_reported_name",
                    });
                }
            } else {
                let mut old_values: Vec<_> = old.iter().map(|s| s.value).collect();
                let mut new_values: Vec<_> = new.iter().map(|s| s.value).collect();
                old_values.sort();
                new_values.sort();
                if old_values == new_values {
                    // The metric multiset did not change; do not invent a pairing
                    // or flood every PR with unchanged same-named methods.
                    continue;
                }
                // No guessed zero, cross-file match, or same-name duplicate pairing.
                let correspondence = if old.len() > 1 || new.len() > 1 {
                    "duplicate_reported_name"
                } else {
                    "counterpart_not_established"
                };
                for (old, new) in old
                    .iter()
                    .map(|s| (Some(s.clone()), None))
                    .chain(new.iter().map(|s| (None, Some(s.clone()))))
                {
                    result.rows.push(Row {
                        metric: label,
                        before: old,
                        after: new,
                        delta: None,
                        correspondence,
                    });
                }
            }
        }
    }
    result.rows.sort_by_key(|row| {
        let anchor = row.after.as_ref().or(row.before.as_ref()).unwrap();
        let severity = row
            .before
            .iter()
            .chain(row.after.iter())
            .map(|s| s.value)
            .max()
            .unwrap();
        (
            row.metric,
            std::cmp::Reverse(severity),
            anchor.path.clone(),
            anchor.name.clone(),
            anchor.line,
            row.before.is_none(),
        )
    });
    if before.primary.provisional || after.primary.provisional {
        result.status = "provisional";
    }
    result
}

impl Changes {
    pub fn markdown(&self) -> String {
        if self.status == "not_requested" {
            return String::new();
        }
        format!(
            "<details>\n<summary>Python function complexity hotspots · {}</summary>\n\n{}\n\n</details>",
            self.status,
            self.markdown_body()
        )
    }

    fn markdown_body(&self) -> String {
        let mut lines = vec![format!("Comparison **{}**.", self.status)];
        if let Some(reason) = self.reason {
            lines.push(format!("Function details unavailable (`{reason}`)."));
            return lines.join("\n");
        }
        lines.push("Metric-changed and unmatched functions; up to five rows per metric, ranked within each metric by the larger reported value. Line shifts alone are omitted. CC and Cog are separate tool observations; unchanged scores do not establish unchanged code.".into());
        lines.push("Same path and unique reported name gives structural correspondence only. For unmatched rows, correspondence is not established (possible move, rename, addition, removal or duplicate name); — means unavailable, never zero. Values are tool units, not percentages.".into());
        if self.rows.is_empty() {
            lines.push("No metric-changed or unmatched functions in the available details.".into());
            return lines.join("\n\n");
        }
        lines.push("\n| Metric | Base location / function | Head location / function | Before | After | Δ | Correspondence |\n|---|---|---|---:|---:|---:|---|".into());
        let location = |site: &Option<Site>| {
            site.as_ref()
                .map(|s| {
                    format!(
                        "`{}:{}` · `{}`",
                        crate::opportunities::encoded(&s.path),
                        s.line,
                        crate::opportunities::encoded(&s.name)
                    )
                })
                .unwrap_or_else(|| "—".into())
        };
        let value = |site: &Option<Site>| {
            site.as_ref()
                .map(|s| s.value.to_string())
                .unwrap_or_else(|| "—".into())
        };
        let mut budget = 12000;
        let mut displayed = BTreeMap::new();
        let mut truncated = false;
        for row in &self.rows {
            let count = displayed.entry(row.metric).or_insert(0);
            if *count == 5 {
                truncated = true;
                continue;
            }
            let text = format!(
                "| {} | {} | {} | {} | {} | {} | {} |",
                row.metric,
                location(&row.before),
                location(&row.after),
                value(&row.before),
                value(&row.after),
                row.delta
                    .map(|v| format!("{v:+}"))
                    .unwrap_or_else(|| "—".into()),
                if row.delta.is_some() {
                    "same path/name"
                } else {
                    "not established"
                }
            );
            if text.len() + 1 > budget {
                truncated = true;
                break;
            }
            *count += 1;
            budget -= text.len() + 1;
            lines.push(text);
        }
        if truncated {
            lines.push("More function observations in JSON `function_changes.rows`.".into());
        }
        lines.join("\n")
    }
}
