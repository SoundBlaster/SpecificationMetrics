use std::fs;
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result, ensure};
use rusqlite::{Connection, params};
use serde::Serialize;

use crate::model::LiveMetricReport;

const CREATE_SCHEMA: &str = "
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    recorded_at_unix_ms INTEGER NOT NULL,
    snapshot_key TEXT NOT NULL UNIQUE,
    root TEXT NOT NULL,
    source_revision TEXT,
    source_digest TEXT NOT NULL,
    counting_rule_version INTEGER NOT NULL,
    specification_definitions INTEGER NOT NULL,
    remaining_opportunities INTEGER NOT NULL,
    ratio REAL,
    state TEXT NOT NULL,
    report_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS snapshots_root_time
    ON snapshots(root, recorded_at_unix_ms DESC, id DESC);
";

#[derive(Debug, Serialize)]
pub struct HistoryEntry {
    pub id: i64,
    pub recorded_at_unix_ms: i64,
    pub report: LiveMetricReport,
}

pub fn save(path: &Path, report: &LiveMetricReport) -> Result<i64> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("cannot create store directory {}", parent.display()))?;
    }
    let connection = Connection::open(path)
        .with_context(|| format!("cannot open metric store {}", path.display()))?;
    connection.execute_batch(CREATE_SCHEMA)?;
    let report_json = serde_json::to_string(report)?;
    let key = blake3::hash(report_json.as_bytes()).to_hex().to_string();
    let now = SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis();
    let now = i64::try_from(now).context("system time is out of range")?;
    connection.execute(
        "INSERT OR IGNORE INTO snapshots (
            recorded_at_unix_ms, snapshot_key, root, source_revision, source_digest,
            counting_rule_version, specification_definitions, remaining_opportunities,
            ratio, state, report_json
        ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11)",
        params![
            now,
            key,
            report.root,
            report.source_revision,
            report.source_digest,
            report.counting_rule_version,
            report.specification_definitions,
            report.remaining_opportunities,
            report.ratio,
            report.state.label(),
            report_json,
        ],
    )?;
    connection
        .query_row(
            "SELECT id FROM snapshots WHERE snapshot_key = ?1",
            [key],
            |row| row.get(0),
        )
        .context("cannot read stored snapshot id")
}

pub fn history(path: &Path, limit: usize) -> Result<Vec<HistoryEntry>> {
    ensure!(
        path.is_file(),
        "metric store does not exist: {}",
        path.display()
    );
    ensure!(limit > 0 && limit <= 1000, "history limit must be 1..=1000");
    let connection = Connection::open(path)
        .with_context(|| format!("cannot open metric store {}", path.display()))?;
    let mut statement = connection.prepare(
        "SELECT id, recorded_at_unix_ms, report_json FROM snapshots
         ORDER BY recorded_at_unix_ms DESC, id DESC LIMIT ?1",
    )?;
    let rows = statement.query_map([i64::try_from(limit)?], |row| {
        let id = row.get(0)?;
        let recorded_at_unix_ms = row.get(1)?;
        let report_json: String = row.get(2)?;
        Ok((id, recorded_at_unix_ms, report_json))
    })?;
    rows.map(|row| {
        let (id, recorded_at_unix_ms, report_json) = row?;
        let report = serde_json::from_str(&report_json).context("invalid stored metric report")?;
        Ok(HistoryEntry {
            id,
            recorded_at_unix_ms,
            report,
        })
    })
    .collect()
}

#[cfg(test)]
mod tests {
    use std::fs;

    use tempfile::tempdir;

    use crate::live::measure;
    use crate::scan::scan;

    use super::{history, save};

    #[test]
    fn snapshots_persist_and_identical_measurements_are_idempotent() {
        let dir = tempdir().unwrap();
        let source = dir.path().join("policy.py");
        let database = dir.path().join("metrics.sqlite");
        fs::write(&source, "if ready:\n    pass\n").unwrap();
        let first = measure(&scan(dir.path(), &[]).unwrap(), None).unwrap();
        let first_id = save(&database, &first).unwrap();
        assert_eq!(save(&database, &first).unwrap(), first_id);

        fs::write(&source, "class Ready(Specification):\n    pass\n").unwrap();
        let second = measure(&scan(dir.path(), &[]).unwrap(), None).unwrap();
        let second_id = save(&database, &second).unwrap();
        assert_ne!(first_id, second_id);
        let entries = history(&database, 10).unwrap();
        assert_eq!(entries.len(), 2);
        assert_eq!(entries[0].report.specification_definitions, 1);
        assert_eq!(entries[1].report.remaining_opportunities, 1);
    }

    #[test]
    fn invalid_utf8_changes_create_distinct_snapshots() {
        let dir = tempdir().unwrap();
        let source = dir.path().join("policy.py");
        let database = dir.path().join("metrics.sqlite");
        fs::write(&source, [0xff]).unwrap();
        let first = measure(&scan(dir.path(), &[]).unwrap(), None).unwrap();
        let first_id = save(&database, &first).unwrap();

        fs::write(&source, [0xfe]).unwrap();
        let second = measure(&scan(dir.path(), &[]).unwrap(), None).unwrap();
        let second_id = save(&database, &second).unwrap();

        assert_eq!(first.parse_issues.len(), 1);
        assert_eq!(second.parse_issues.len(), 1);
        assert_ne!(first.source_digest, second.source_digest);
        assert_ne!(first_id, second_id);
    }
}
