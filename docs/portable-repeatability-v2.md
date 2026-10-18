# Portable repeatability preparation v2

Use `paired_reference_repeatability_v2.py --freeze <new-directory>` for a future
repeatability preparation. Generated prompts name four repository-relative paths
and explicitly use repository-root working directory. Their bytes/hashes are
generated before dispatch and need no machine-specific rewriting. V2 verifies
those exact generated prompts; it does not copy historical absolute prompts.

First-arm order uses stable sorted case index plus repeat number, independently
of the shuffled case position. Every case flips first arm between adjacent
blocks; each block has two baseline-first and two retrieval-first cases. There
are still 24 fresh contexts and unchanged same-view denominators. No annotation
or paid dispatch is authorized by preparation.

The old v1 preparation and executed Sol results remain immutable diagnostic
evidence. Its R03/R04 first-arm orders did not alternate; order/time effects are
therefore unestimated. The unanimous labels remain observed model-specific
agreement, not proof of counterbalanced execution or independent semantic truth.
Do not relabel the historical run as v2 or rerun Sol merely to hide that limitation.
An actual new counterbalanced measurement requires a new approved run.
