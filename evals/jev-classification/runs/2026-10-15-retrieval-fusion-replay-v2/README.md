# Fusion v2: repair without new inference

**Status:** post-failure development replay of the unchanged 518-document index
and 16 bilingual queries. Original v1 H2 remains failed. Source vectors, packet
and v2 producer are bound by SHA-256 in `replay.json`.

## Root cause and discriminating comparison

V1's ASCII tokenizer discarded Cyrillic. Its full-corpus RRF then awarded lexical
votes to zero-score documents ordered by ID. Six Russian queries had no lexical
matches at all, yet this unsupported channel still reordered dense retrieval.

Change two factors independently:

1. Preserve Unicode letters/numbers while keeping camel-case/underscore splits.
2. Contribute only **strictly positive** BM25 scores to RRF. When that list is
   empty, the hybrid order is exactly the dense order. Nonpositive values are
   deliberately excluded; this is an explicit policy for this BM25 implementation,
   not a universal claim about every lexical scoring function.

| Arm | Russian hybrid768 top-5 /8 | Russian hybrid256 top-5 /8 |
|---|---:|---:|
| Original ASCII + full RRF, exact frozen control | 3 | 3 |
| Unicode only + full RRF | 3 | 3 |
| Original tokenizer + positive BM25 votes only | 8 | 7 |
| Unicode + positive BM25 votes only | 8 | 7 |

The ranking recovery is attributable to removing unsupported RRF votes in this
controlled replay. Unicode support fixes text loss but does not translate Russian
terms into English source tokens, so it alone does not improve this result.
Dense vectors and rankings are unchanged. English hybrid top-5 remains 7/8 under
all arms. No provider call or new model encode occurred.

## Important residual failure

The Russian path query contains the English word **Windows**. BM25 finds
`quiet_progress_windows_for_reasoning`, which uses **windows** in the time-window
sense. It gets one legitimate lexical match but is wrong for the requested path
decision. Corrected hybrid768 ranks it first and the intended `safe_workspace_path`
second; dense768 alone puts the intended function first.

Thus “positive lexical evidence” prevents arbitrary zero-tail votes, but does not
prove semantic relevance. The corrected hybrid is still not universally better
than dense. Keep both outputs available for evaluation; do not introduce a
language-specific override or tune weights on these known answers.

## Replay

Install only `requirements-retrieval-replay.txt` in the repository evaluation
environment, route local caches using `tb5-build-cache`, then run:

```sh
python -W error -m unittest -v test_retrieval_fusion_replay_v2.py
python retrieval_fusion_replay_v2.py
```

The default command verifies the existing output. `--write` is used once to create
a fresh package and refuses to overwrite an existing directory. CI runs the
default replay without model libraries or inference.

Next validation must use new source-grounded queries. This repair is checked
against the original failure plus synthetic regression tests, not an independent
production-quality evaluation. No ownership acceptance or S/U change follows.
