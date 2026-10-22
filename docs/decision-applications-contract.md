# FirstMatch application diagnostics v1

```sh
specification-metrics application-sites PYTHON_IMPORT_ROOT \
  --profile python-decisions-v1 --scope-manifest scope.toml --output decisions.json
```

The opt-in profile is `specification-metrics.python-decision-applications/v1`.
Default/explicit `python-if-v1` and its JSON contract remain unchanged. Both
profiles have `metric_effect: "none"`. Counting rule v9, raw S/U, registries,
collection/store formats and merge gates remain unchanged.

## Unit and categories

Inventory syntactic `.decide(...)` calls throughout selected UTF-8 Python
sources: assignments, returns, arguments and conditions. Confirm module constants
constructed through imported synchronous `specification_core.FirstMatch(...)`
or `FirstMatch.with_fallback(...)`, including constructor/module aliases and
explicit static re-exports. Method names alone do not establish application.
`PredicateSpec.decide` is unresolved; `FirstMatch.is_satisfied_by` remains
unresolved in the old Boolean profile.

| Category | Meaning |
| --- | --- |
| `direct_application` | Receiver resolves and the result, optionally projected through `.value`/`.matched`, is assigned, returned, passed as an argument or left standalone. A sole `.matched` if-condition also qualifies. |
| `mixed_expression` | Receiver resolves but surrounding syntax adds processing: comparisons, conditional expressions, Boolean composition or further attribute/method chains. |
| `unresolved_call` | A supported FirstMatch binding cannot be proven; uncertainty takes precedence over result shape. |

These describe **local result consumption**, not entire if conditions. The unit
differs from the Boolean-if profile:

```text
examined_decide_calls = direct_application + mixed_expression + unresolved_call
```

`projection` records an immediate `.value`/`.matched` access, ignoring parentheses.
`consumer` is binding, return, argument, standalone, boolean_guard or embedded.
`bound_to` records an immediate identifier assignment. Later branch dependencies
are not inferred:

```python
result = RULE.decide(ctx).value  # direct; bound_to=result
if result:                      # no inferred connection to this branch
    report(result)
value = RULE.decide(ctx).value if enabled else None  # mixed, not a policy verdict
```

`if RULE.decide(ctx)` is mixed/embedded: MatchResult is not the Boolean
Specification API. `.value` may be None; the diagnostic does not prove a matched
check, fallback, valid arguments, runtime execution, correctness, requirement
fulfillment or semantic coverage. Mixed is not a refactoring instruction.

## Provenance

Only scanner-selected source bytes are used. No imports, execution or inference.
Source/scope digests must match before joining with primary reports. Preserve
role, parse and marker issues; `provisional: false` only confirms those scanner
prerequisites. Non-Python/undecodable files count as unsupported source files.

Each call retains receiver, method, factory target or uncertainty reason,
relative path and 1-based UTF-8 byte start/end anchors (end exclusive). The call
ends at its closing parenthesis, before projection. `application_id` is BLAKE3
over domain `python-decision/v1`, the selected-source digest, path and call byte
offsets separated by NUL. It identifies an exact snapshot, not a stable
cross-revision candidate/registry key. Calls are not subtracted from U.

## Import roots and limitations

For nonstandard layouts choose the Python import root as measurement root. The
shared resolver maps relative paths, with existing `src/` normalization and
package initializer handling. It does not infer arbitrary sys.path/environment
modifications. SpecGraph's absolute `publication_evidence.*` imports require
root `SpecGraph/tools`. Different roots/scopes are different measurement
contracts; selecting definitions alone may still leave imports unresolved.

Reassignment, shadowing, observed mutations, missing/ambiguous modules, cycles,
wildcard/conditional imports and parse errors preserve uncertainty. Inline/local
instances, custom DecisionSpec classes, generic constructor subscripts and async
decisions are unsupported. Lambda/comprehension calls are inventoried but
unresolved. Arbitrary external monkey-patching/import hooks remain outside the
static assumptions. Additional composition such as negated `.matched` guards
is conservatively embedded in this first profile.

Next separate analysis: track bound results to branch consumers with scope,
reassignment and control-flow checks before proposing uses_specification
exclusions. A conservative subset is now available through the separate
[`python-decision-flow-v1` profile](decision-flow-contract.md); this call-inventory
profile keeps its existing contract. See the [frozen pilot](firstmatch-application-pilot.md).
