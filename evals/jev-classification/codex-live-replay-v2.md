# Codex capture replay v2

Review of PR #90 found two confirmed consumer defects: v1 accepted labels outside
the frozen response schema and trusted a hard-coded agreement count after coherent
capture rebinding. The original capture, receipts, producer and v1 replay remain
unchanged. `verify_codex_live_v2.py` adds schema validation and derives the summary
from the axis rows before invoking the historical binding checks.

Run `python -B -m unittest -v test_verify_codex_live_v2.py` from this directory.
The three offline regressions replay the genuine observation and reproduce both
blind spots on temporary, coherently rebound copies. Those copies pass v1 and
fail v2. No inference is involved. The recorded observation remains 3/4 axes,
with the ownership disagreement preserved; this is not semantic accuracy.
