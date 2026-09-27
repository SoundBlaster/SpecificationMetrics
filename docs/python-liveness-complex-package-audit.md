# Python liveness: complex package audit

This note records read-only scans used to stress Python liveness against real
package layouts. Repositories are pinned to the audited commits. No upstream
source was copied into SpecificationMetrics. The scans are static analysis;
they do not import or execute target packages.

## SpecificationCore Python port

Audited [`SoundBlaster/SpycificationCore`](https://github.com/SoundBlaster/SpycificationCore)
at commit [`6113d77`](https://github.com/SoundBlaster/SpycificationCore/commit/6113d773e78cb94c4eb0ce31e8439877fef45494).
The production-only source scan covered 4 Python files and found 42 decision
sites and 19 Specification declarations: 7 `live`, 12 `unknown`, no parse or
scope issues. This is discovery evidence, not a closed-world health score:
public exports and uses outside `src` remain outside the scan boundary.

A second scan included `src` and `tests` solely to exercise consumer resolution.
It covered 6 Python files and found 42 decision sites, 19 class declarations,
and 17 test factory sites. All 36 liveness entries resolved `live`, including
parameterized generic construction such as `AlwaysTrue[int]()` and class
factory calls such as `FirstMatch.with_fallback(...)`. Test files are not
production application scope, and their factory sites must not be interpreted
as production Specification inventory.

Reproduction after checking out the pinned commit:

```sh
cargo run --locked -- scan /tmp/SpycificationCore --include src \
  --output /tmp/core-source.json
cargo run --locked -- scan /tmp/SpycificationCore --include src --include tests \
  --output /tmp/core-source-and-tests.json
```

The first scan exercises public API uncertainty; the second exercises runtime
use resolution through the package's `__init__.py` re-exports and the tests'
imports. These are intentionally separate interpretations of the source
boundary.

## Larger-package stress scans

| Repository and commit | Python files | Decision sites | Recognized Specification declarations | Parse/scope issues |
| --- | ---: | ---: | ---: | ---: |
| [`zspec`](https://github.com/zlibs-community/zspec/tree/6f5dee100ae1ea0bdbc6a29fb9ad43128119b132) `6f5dee1` | 17 | 88 | 8: 7 `live`, 1 `unknown` | 0 / 0 |
| [`mellea`](https://github.com/generative-computing/mellea/tree/1276bf6a5fb2e29b19e089776855217e6c073493) `1276bf6` | 150 | 2,546 | 0 | 0 / 0 |
| [`spec-classes`](https://github.com/matthewwardrop/spec-classes/tree/d8e0123ee0488a92cc4112946874108298d16fea) `d8e0123` | 33 | 511 | 0 | 0 / 0 |

The `zspec` result is a liveness sample; its remaining `unknown` is documented
in the [earlier bounded audit](python-liveness-real-package-audit.md). Mellea
and spec-classes are parser and candidate-discovery stress scans only: no
declaration matched the current inheritance-based Specification recognizer,
so these scans do not produce a Specification liveness ratio. A zero here
means “not recognized by this contract,” not “the package has no rules or
specifications.”

The audit supports two bounded conclusions. First, the analyzer resolves the
tested generic constructors and class factories through package re-exports.
Second, larger packages can produce useful candidate inventories without
parse/scope errors, but packages that express specifications through different
APIs need a separately designed declaration contract before their liveness
can be measured.
