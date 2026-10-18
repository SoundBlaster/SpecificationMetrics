# Jev4Mellea 0.9.0 evaluation baseline

## Dependency

The current evaluation environment uses `mellea-jev-adapter[openai]` 0.9.0,
[release v0.9.0](https://github.com/SoundBlaster/Jev4Mellea/releases/tag/v0.9.0),
pinned to commit `e94d6ba1808b95208ef8ac05da7b256f3988532f` in
`evals/jev-classification/requirements-evaluation.txt` and its resolved lock.
Python remains >=3.11. Other locked package versions are retained from the
preceding environment to isolate the adapter update.

This is the Jev adapter release. IBM Mellea is an optional extra in that package;
its supported upstream range remains `>=0.7.0,<0.9.0`. SpecificationMetrics uses
the adapter's `openai` extra and does not install the optional Mellea runtime.
The new native categorical providers and Mellea Requirement bridge are available
in the release; this dependency update does not switch the existing Responses
consumer to either API or enable automatic semantic acceptance.

## Current environment

Use the repository `.venv` with the current lock:

```bash
.venv/bin/python -m pip install -r evals/jev-classification/requirements-evaluation.lock
cd evals/jev-classification
../../.venv/bin/python -W error -m unittest -v test_jev4mellea_compatibility.py
../../.venv/bin/python -W error -m unittest -v \
  test_recommendation_policy_v1.py test_retrieval_fact_adapter_v1.py test_coreinfra_transport.py
```

Follow the local build/cache routing instructions before installing or testing.
The `evaluation-sdk-current` CI job installs this lock in a fresh Python 3.11
environment and runs both commands without hosted inference or credentials.

## Historical replay boundary

`requirements-categorical-pilot.txt` and `.lock` remain unchanged at 0.8.0.
The frozen ordinary-Luna preparation records these files, the SDK source trees
and installed versions. Its verifier deliberately rejects a different SDK;
upgrading its lock in place would invalidate provenance rather than reproduce
the experiment. The existing `check` CI job installs that historical lock and
continues to run its exact replay and the broader repository checks.

To replay locally, use a **separate** Python 3.11 environment installed from the
historical lock. Invoke that environment's interpreter from
`evals/jev-classification`:

```bash
<historical-environment>/bin/python -W error -m unittest -v test_categorical_luna_pilot_v1.py
```

Do not install both locks into one environment. In particular, broad unittest
discovery includes incompatible exact-version checks; use the explicit current
or historical suites above. Source, receipts, labels and recorded metrics of
prior experiments are preserved.

## What compatibility proves

The new offline suite anchors the captured fixture to its result-receipt hash,
checks its request/response file hashes, verifies the installed release and Git
commit, and exercises the public SDK through an in-memory HTTP transport:

- All eight categorical tasks must preserve their state and questions and render
  byte-identical requests.
- All eight recorded responses must decode to the complete historical result
  records, including labels, model identity, usage and settings.
- Incomplete and refused responses must still raise their typed errors after a
  single mock dispatch.

This is a consumer compatibility check, not a new live run, provider accuracy
measurement or validation of newly introduced native/Requirement APIs. No new
model calls are authorized or required by the upgrade.
