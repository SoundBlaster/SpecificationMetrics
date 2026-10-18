# Truncated-capture comparison diagnostics v2

Use `sol_top_line_comparison_v2.py --score <run> --output <new-file>` for new
operational reports. Historical v1 source, contracts and saved reports remain
immutable; v1's incomplete-score reader can fail on a partial last JSONL record.

V2 counts complete JSON records in the captured prefix and reports a final
unterminated fragment separately with line/size/digest. It never repairs bytes
or ignores malformed interior/newline-terminated records. Syntactic capture count
is not a verified response count. Incomplete runs retain all planned denominators
and produce no complete-cohort agreement. The prefix transport audit remains
visible separately. Complete saved runs yield the same provider comparisons as
v1. No missing observation becomes a wrong domain label or model abstention.
