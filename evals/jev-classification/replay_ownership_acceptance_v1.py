"""Exercise the ownership handoff against the pinned BDD source, without inference."""
import argparse
import json
from pathlib import Path

import conditional_native_action_v2 as prep
from recommendation_policy_v1 import evaluate
from recommendation_policy_v1.context import Facts, LookupFact, OwnershipFact, Role, Source, ToolFact
from ownership_acceptance_v1.adapters import pinned_bdd, sha

ROOT = Path(__file__).resolve().parent
RUN = ROOT / 'runs/2026-10-15-ownership-acceptance-v1'


def replay():
    artifacts = prep.old.previous.source.verify()
    examples = json.loads(artifacts['integrator-examples.json'])['annotations']
    example = next(row for row in examples if row['case_id'] == prep.old.BDD)
    origin = Source(artifact=str((prep.old.previous.source.RUN / 'integrator-examples.json').relative_to(ROOT)),
                    sha256=sha(artifacts['integrator-examples.json']), locator=prep.old.BDD,
                    authority='development_premise')
    # Deliberately start without ownership evidence to exercise the handoff. This
    # is a counterfactual replay, not a newly discovered bug or an accuracy result.
    initial = Facts(case_id=example['case_id'], state_sha256=example['state_sha256'],
                    scope_binding_sha256=example['scope_binding_sha256'],
                    role=Role(kind=example['concern_kind'], support=example['evidence_confidence'], sources=(origin,)),
                    ownership=OwnershipFact(value='unknown'), tool_responsibility=ToolFact(value='unknown'),
                    intent_lookup=LookupFact(value='completed', sources=(origin,)))
    accepted = pinned_bdd(initial)
    updated = Facts.model_validate_json(json.dumps(accepted['facts']))
    files = [Path(__file__), ROOT / 'ownership-fact-acceptance-v1.md']
    files += sorted((ROOT / 'ownership_acceptance_v1').glob('*.py'))
    return dict(contract='specmetrics.ownership-acceptance-replay/v1',
                status='offline_counterfactual_handoff_not_new_discovery',
                before=evaluate(initial), acceptance=accepted, after=evaluate(updated),
                producer_sha256={str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in files},
                source_snapshot_sha256=prep.SOURCE_SHA256, source_revision=prep.REVISION,
                provider_requests=0, metric_effect='none', semantic_accuracy=None,
                negative_ownership_approved_on_real_project=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    raw = prep.encoded(replay())
    if args.write:
        RUN.mkdir(parents=True, exist_ok=False)
        with (RUN / 'report.json').open('xb') as stream:
            stream.write(raw)
    else:
        prep.require((RUN / 'report.json').read_bytes() == raw, 'ownership replay differs')
    print('Offline ownership handoff verified: pinned BDD reuse, zero requests; no project-wide absence claim.')


if __name__ == '__main__':
    main()
