# Python liveness: real-package audit

This note records a bounded source-level audit of import and export patterns.
It is a smoke test of the current static analyzer, not proof that every
Specification use in a package is resolved. The audit was performed on
2026-09-26.

## `zspec` source package

Scanned [`zlibs-community/zspec`](https://github.com/zlibs-community/zspec) at
commit [`6f5dee1`](https://github.com/zlibs-community/zspec/commit/6f5dee100ae1ea0bdbc6a29fb9ad43128119b132),
the source for its 1.8.4 release. Its package root explicitly re-exports names
from implementation modules with `from ... import ... as ...`; its core module
defines the `Specification` base and concrete composite specifications.

Reproduction from the repository root:

```sh
git clone https://github.com/zlibs-community/zspec.git /tmp/zspec-audit
git -C /tmp/zspec-audit checkout 6f5dee100ae1ea0bdbc6a29fb9ad43128119b132
cargo run -- scan /tmp/zspec-audit --include src/zspec \
  --output /tmp/zspec-liveness.json
```

Observed result: 17 Python source files, 8 recognized Specification
declarations, 7 `live`, 1 `unknown`, and no parse or source-scope issues. The
unknown declaration is `CachingSpecification`; the scanner did not find a
resolved runtime use in the selected source tree. The seven concrete
specifications have resolved runtime uses in their implementation, including
`isinstance` checks over tuples of types, `match` class patterns, and a
string-to-type registry. Because this is a public library and the audit did not
supply a closed-world manifest, it does not establish that the unknown
declaration is dead or that external consumers are absent.

The source audit found no module-level `__getattr__` and no intra-package import
cycle among the 17 Python modules. The import-cycle check uses Python's AST and
resolves only statically named modules inside `src/zspec`; dynamic imports and
runtime hooks are outside that check. The upstream repository has no declared
license file at the audited commit; this audit does not copy or vendor its
source.

## Dynamic exports and cycles

The versioned acceptance corpus also covers two real Python mechanisms:

- NumPy's [`numpy/core/__init__.py`](https://github.com/numpy/numpy/blob/main/numpy/core/__init__.py)
  defines module-level `__getattr__` and delegates attribute lookup to `_core`.
  A module-level hook can expose names that static import resolution cannot
  enumerate, so plausible Specification declarations remain `unknown`. The
  `python.dynamic_getattr_export` fixture checks this even when the hook body
  does not call a recognized reflection builtin.
- CPython's [circular-import FAQ](https://docs.python.org/3/faq/programming.html#how-can-i-have-modules-that-mutually-import-each-other)
  documents top-level `from module import name` cycles and the partially
  initialized-module failure mode. The `python.circular_reexport` fixture
  exercises a re-export cycle and requires `unknown`, never `dead`.

The analyzer does not execute packages to decide liveness. Dynamic exports,
cyclic resolution, and code outside the reviewed source boundary stay
conservative; the fixtures validate that these patterns cannot silently lower
the live Specification count.
