# Local EmbeddingGemma 2 retrieval pilot

## Question and authority

Can a small local embedding model retrieve a known SpecGraph refactoring
counterpart from procedural code or a short description of intent? Compare
lexical BM25, dense cosine and their equal-weight reciprocal-rank fusion (RRF,
constant 60), using 768 and 256 dimensions from the same model execution.

This evaluates candidate discovery. A hit is a **historical counterpart**, not
a verified equivalent Specification. Neither similarity nor an empty result
establishes ownership. Results remain `ranked_candidates` under
[ownership acceptance v1](ownership-fact-acceptance-v1.md); no facts are accepted,
no production S/U counts change, and Jev/Luna receive no new requests.

## Frozen scope

- Source: the existing 60-site development corpus, verified with
  `build_specgraph_corpus.py --check` against pinned Git objects.
- Queries: 15 pre-refactoring excerpts, each also expressed by one hand-authored
  English intent query. These queries were written with knowledge of the corpus.
- Index: their 15 post-refactoring counterparts and 30 distractor excerpts from
  the same corpus, 45 documents total. Original before excerpts are excluded;
  exact excerpt-hash overlap is rejected. Similar identifiers and structure
  across before/after remain deliberately present.
- Pair identity comes from selection history, not expected semantic labels.
  Each query has one designated historical counterpart; other relevant hits
  have not been exhaustively judged.
- Eight pairs share the lifecycle family. Report this cluster separately so
  correlated easy examples do not masquerade as independent observations.
- Embedding text contains only source code, path and symbol title. Expected
  labels, rationales, family IDs and reference answers are not embedded.

This is a development pilot, not a holdout, whole-repository coverage test or
benchmark against other embedding models. It cannot estimate production false
positives, prove absence of an existing Specification, or prove that retrieved
code has the same intent. No confidence intervals from 30 independent samples:
there are 15 paired sites and additional family correlation.

## Model and execution

`google/embeddinggemma-2`, revision
`914f7f89142e33e77833254d9c9b90c3cef7303b`, Apache-2.0.
Text/code encoder only (`vision_config=None`, `audio_config=None`), float32.
Query prompt: `CodeRetrieval`; document input:
`title: <path>::<symbol> | text: <source>` with no extra prefix.
The pinned model provides an 8192-token window; reject oversized inputs instead
of silently truncating them. Normalize 768d embeddings and renormalize their
first 256 coordinates for the MRL comparison. This changes vector storage and
scoring cost, **not encoder inference cost**.

The user approved local inference. Public weights are downloaded without an
implicit Hugging Face token; source code stays local. One warm-up, one document
batching pass (batch size four), and 30 individually timed query encodes.
The same embeddings serve every ranking variant. No tuning or retries based on
retrieval quality. Runtime failures get their own preserved failure record.

Official references:
[Google model card](https://ai.google.dev/gemma/docs/embeddinggemma/model_card_2?hl=en),
[developer guide](https://developers.googleblog.com/embeddinggemma-2-the-developer-guide/),
[pinned checkpoint](https://huggingface.co/google/embeddinggemma-2/tree/914f7f89142e33e77833254d9c9b90c3cef7303b).
SpecGraph source excerpts retain the corpus's Apache-2.0 provenance and
[license](corpus/LICENSE.SpecGraph).

## Measures and interpretation

For code and intent queries separately, record counterpart Recall@1/5/10 and
MRR. With one designated reference, Recall@k is the fraction of queries whose
counterpart appears among the first k results. Inspect failures by site and
family; a different top result is not automatically semantically wrong.

Record model download, loading, index encoding, per-query encoding and total
ranking time separately. Report median/p95 query latency as a small-run
observation, not a service SLA. RSS is the process-lifetime high-water mark;
MPS current and driver allocations at run end are separate snapshots and must
not be added to RSS on unified-memory hardware or called GPU peak memory.

Save packet, vectors, full rankings, receipt, package versions and source
verification. Offline replay checks packet/producer/vector digests and recomputes
rankings without model dependencies or network. A vector snapshot permits replay;
an incremental production repository index is outside this pilot.

## Reproduction

From `evals/jev-classification`, using a separate environment:

```sh
../../.venv/bin/python -m venv ../../.venv-embedding
../../.venv-embedding/bin/python -m pip install -r requirements-embeddinggemma.txt
../../.venv-embedding/bin/python -W error -m unittest -v test_embeddinggemma_pilot_v1.py
# Explicit local execution; choose a fresh output directory on each attempt.
../../.venv-embedding/bin/python embeddinggemma_pilot_v1.py \
  --execute runs/<fresh-run-name> --source-repo /path/to/SpecGraph --device mps
```

CPU execution is available through `--device cpu`; no silent device fallback.
For offline replay, install only `requirements-retrieval-replay.txt` and run
`embeddinggemma_pilot_v1.py --verify runs/<completed-run-name>`.
CI must replay saved vectors only; it must not download a model or run inference.

## Environment findings before inference

1. On this macOS 27 arm64 / Python 3.10 environment, importing
   `sentence_transformers` with SciPy 1.15.3 failed in `_propack/_spropack`:
   `section '__DATA/__thread_bss' has a zero-fill section type, but offset field
   is not zero`. The loader rejected the wheel's native image. The upstream
   packaging/linker cause is not established. Pinning SciPy 1.14.1 restored the
   same import; Torch 2.14.1 reported MPS available. This is an environment result,
   not model failure. The pinned environment and import smoke check prevent an
   unnoticed recurrence on this machine.
2. NumPy 2.2.6 float32 BLAS matrix multiplication emitted overflow/divide-by-zero
   warnings on normalized synthetic inputs. The backend cause is unresolved.
   For this small corpus, cosine now uses explicit fixed-order float64 `einsum`
   without BLAS and rejects nonfinite scores. The synthetic ranking and 256d
   renormalization tests pass with warnings treated as errors. This is not a
   general BLAS performance comparison or a claim that all matmul outputs failed.
3. The first execution failed before embedding because the common
   `EmbeddingGemma2Processor` required Pillow. After installing Pillow, the next
   attempt failed because its video subprocessor required Torchvision. In
   Transformers 5.20.0, processor construction loads these components even when
   the model's vision/audio encoder configs are disabled. Both failure receipts
   are retained under `runs/2026-10-15-embeddinggemma-retrieval-v1*`; their frozen
   inputs and producer hash are unchanged. Pin the processor dependencies too.
   A successful full text encode, rather than import alone, is the compatibility
   smoke test. No images, audio or video are submitted by this pilot.
