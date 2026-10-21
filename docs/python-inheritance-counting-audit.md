# Python inheritance counting correction (v9)

## Reproduction and provenance

The first retained SpecGraph metric artifact exposed a discovery/liveness gap:
[`39639808647`, artifact `12365191884`](https://github.com/0al-spec/SpecGraph/actions/runs/39639808647/artifacts/12365191884).
The original ZIP SHA-256 was verified against GitHub metadata:
`bd38f98f1b42d95e2d4c452ac64cd631a6ef18428836935a56ffe4a6db0482bb`.
The frozen artifact is unchanged.

The head source revision was
`0al-spec/SpecGraph@b86895c9c3ad935fef6276671d2e188dd11ae3e1`, measured under
`scopes/specificationmetrics.toml`. The pinned analyzer was
`c4d95427875d28870085c847852f7357859d164f` (counting rule v8).
The reproduction uses the exact same Git revision, source digest
`b7fd9e9749a77ff388f18867adfea508817595c36b67a9efd5cc82f1aa87270e`, and
scope-manifest digest. No application source was edited or executed.

## Root cause

The source has an ordinary Specification family:

```python
class BDDPolicy(Specification[BDDContext]):
    ...

class BDDScenarioFieldsSpec(BDDPolicy):
    ...
```

v8 recognized `BDDPolicy`, but did not propagate recognition to subclasses.
Its liveness runtime-use whitelist omitted class bases. Consequently the base
was `unknown`, six production subclasses were absent from `S`, and their
internal branches remained in `U`, although all six constructors appeared in
`tools/native_bdd/composition.py`.

The six recovered declarations and newly covered candidate counts are:

| Module under `tools/native_bdd/` | Declaration | Candidates removed from U |
|---|---|---:|
| `fields_spec.py` | `BDDScenarioFieldsSpec` | 2 |
| `ids_spec.py` | `BDDScenarioIDsSpec` | 2 |
| `presence_spec.py` | `BDDContainerPresenceSpec` | 7 |
| `profile_spec.py` | `BDDProfileSelectionSpec` | 2 |
| `references_spec.py` | `BDDScenarioReferencesSpec` | 3 |
| `values_spec.py` | `BDDScenarioValuesSpec` | 4 |
| **Total** | **6 declarations** | **20** |

## Result on the unchanged source snapshot

| Counter | Original v8 | Corrected v9 |
|---|---:|---:|
| Scanned candidates | 10,097 | 10,097 |
| Candidates inside Specifications | 4 | 24 |
| S | 100 | 106 |
| Live Specifications | 99 | 106 |
| Unknown Specifications | 1 | 0 |
| U | 10,093 | 10,073 |
| S/U | 0.00990785693 | 0.01052318078 |
| Provisional | true | false |

The corrected CLI passed `measure --require-complete`. This is a primary S/U
remeasurement; supplementary complexity/clone tools were not rerun. The result
corrects the analyzer rather than measuring a source refactoring improvement.
Counting-rule v9 changes the collection contract digest, so normal `compare`
must reject a v8/v9 collection comparison. Preserve historical snapshots and
annotate this migration separately.

## Prevention and limits

`src/liveness/python_inheritance.rs` contains a reduced BDD-family regression,
transitive/generic/alias/re-export cases, marker inheritance, unseeded cycles,
and negative cases for conflicting, conditional, function-local, wildcard,
rebound and cyclic re-export bindings. These exercise discovery, inherited
runtime use, S/U and sibling branch preservation together.

Discovery reaches a fixed point from recognized native/marker declarations.
Only statically resolved module-level ancestry is promoted. It does not
interpret Python execution, arbitrary mutations, dynamic base expressions or
nested class qualification. A non-provisional result means this supported
analysis completed, not that all possible Python metaprogramming was understood.

SpecGraph CI continues using its existing analyzer pin until a separate
consumer update is reviewed. Merging this correction alone does not change
previously published SpecGraph metric comments.
