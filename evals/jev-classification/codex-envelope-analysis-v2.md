# Interrupted envelope run analysis v2

PR #91 review identified a confirmed consumer failure: the transport counts a
dispatched logical request before its sender returns, but v1 requires a response
row for every counted request. A sender exception or interruption therefore
prevents the preserved run from being diagnosed as incomplete.

`codex_envelope_analysis_v2.py` is an offline-only consumer. It retains all frozen
producer/manifest/capture bindings and accepts at most one missing final response
when the receipt explicitly records an interrupted, incomplete ledger. It names
that request, preserves available observations, and returns
`incomplete_not_evaluable` with no hypothesis result or automatic fact acceptance.
This is an accounting change, not a new acceptance of semantic results. Scoring
of the completed capture is unchanged. v1 producer, analyzer and raw files remain
byte-for-byte intact.

Run `python -B -m unittest -v test_codex_envelope_analysis_v2.py` here, or
`python -B codex_envelope_analysis_v2.py --directory <preserved-run>` to print a
diagnostic without writing over the historical comparison. Regressions use
synthetic senders raising RuntimeError/KeyboardInterrupt before or after one
response, reject two missing rows and false completeness, and compare the genuine
completed observation to its frozen v1 scoring. No inference is performed.
