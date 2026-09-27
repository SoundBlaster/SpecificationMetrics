# Rust liveness: real-package smoke audit

This read-only audit used the local SpecHarvester source corpus to check that
the Rust scanner can traverse representative crate layouts. The corpus contains
108 repository checkouts, 17 of which have a `Cargo.toml` at the checkout root.

Four established Rust projects were scanned at their current local checkout
revisions. Each scan selected one production source subtree with `--include`;
the JSON reports were written under `/tmp` and were not added to this repository.

| Checkout | Revision | Selected subtree | Application files | Parse issues | Scope issues | Specification declarations |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `tokio-rs-tokio` | `df28ffe6` | `tokio` | 556 | 0 | 0 | 0 |
| `serde-rs-serde` | `747814f7` | `serde` | 6 | 0 | 0 | 0 |
| `clap-rs-clap` | `d93a00d6` | `clap_builder` | 57 | 0 | 0 | 0 |
| `burntsushi-ripgrep` | `f9c05a9` | `crates/searcher` | 11 | 0 | 0 | 0 |

The source scan also found no `specmetrics: specification/v1` marker or native
SpecificationCore trait implementation in any of the 17 Rust checkouts. These
projects therefore provide parser and crate-layout smoke coverage, not examples
of live/dead Specification classification. The versioned acceptance fixtures
remain the evidence for those statuses and cover cross-file crate paths, inline
modules, construction, private dead declarations, public declarations, aliases,
type-only references, unresolved trait-object lookup, and static registration.

Re-run with the checkout corpus under `$P53Sources`:

```sh
specification-metrics scan "$P53Sources/tokio-rs-tokio" \
  --include tokio --output /tmp/tokio-rust-scan.json
specification-metrics scan "$P53Sources/serde-rs-serde" \
  --include serde --output /tmp/serde-rust-scan.json
specification-metrics scan "$P53Sources/clap-rs-clap" \
  --include clap_builder --output /tmp/clap-rust-scan.json
specification-metrics scan "$P53Sources/burntsushi-ripgrep" \
  --include crates/searcher --output /tmp/ripgrep-searcher-rust-scan.json
```

An empty declaration list is not a zero or dead liveness result. It means these
projects do not currently declare the metric's recognized Specification
abstraction.
