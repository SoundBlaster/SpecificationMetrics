"""Replay established development premises beside raw native actions, offline."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import conditional_native_action_v2 as prep
from recommendation_policy_v1 import evaluate
from recommendation_policy_v1.context import Facts, LookupFact, OwnershipFact, Role, Source, ToolFact
from recommendation_policy_v1.proposals import task

ROOT = Path(__file__).resolve().parent
LIVE = ROOT / 'runs/2026-10-15-conditional-native-action-live-v2'
HISTORICAL_RUN = ROOT / 'runs/2026-10-15-formal-recommendation-policy-v1'
RUN = ROOT / 'runs/2026-10-15-formal-recommendation-policy-v1-1'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source(path, raw, locator, authority='development_premise'):
    return Source(artifact=str(path.relative_to(ROOT)), sha256=sha(raw), locator=locator, authority=authority)


def replay():
    # Re-execute historical verification without editing the producer or results.
    spec = importlib.util.spec_from_file_location('conditional_live_verifier', LIVE / 'verify_results.py')
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    historical = verifier.analyze()
    prep.require(json.loads((LIVE / 'analysis.json').read_bytes()) == historical, 'historical analysis differs')
    frozen = prep.verify()
    examples_run = prep.old.previous.source.RUN
    example_files = prep.old.previous.source.verify()
    examples = json.loads(example_files['integrator-examples.json'])['annotations']
    cases = {c['case_id']: c for c in json.loads(example_files['packet.json'])['cases']}
    report = prep.inspect(LIVE)
    results = []
    for example in examples:
        case_id = example['case_id']
        origin = source(examples_run / 'integrator-examples.json', example_files['integrator-examples.json'],
                        case_id)
        role = Role(kind=example['concern_kind'], support=example['evidence_confidence'], sources=(origin,))
        ownership = OwnershipFact(value='unknown')
        tool = ToolFact(value='unknown')
        if case_id == prep.old.BDD:
            # verify() bound this witness to full modules, class containment and target AST.
            owner_source = source(prep.RUN / 'ownership-witness.json', frozen['ownership-witness.json'],
                                  'BDDScenarioValuesSpec.findings -> BDDPolicy._evaluate', 'source_binding')
            ownership = OwnershipFact(value='existing_specification', sources=(owner_source,))
        if case_id == 'target-04-cell01':
            prep.require(example['basis'] == 'tool_responsibility', 'tool premise changed')
            tool = ToolFact(value='yes', sources=(origin,))
        facts = Facts(case_id=case_id, state_sha256=cases[case_id]['state_sha256'],
                      scope_binding_sha256=cases[case_id]['scope_binding_sha256'], role=role,
                      ownership=ownership, tool_responsibility=tool,
                      intent_lookup=LookupFact(value='completed', sources=(origin,)))
        decision = evaluate(facts)
        observations = []
        for row in report['rows']:
            if row['case_id'] != case_id:
                continue
            labels = row['prediction']['labels']
            observations.append(dict(request_id=row['request_id'], provider=row['provider'], arm=row['arm'],
                                     raw_labels=labels, raw_tuple_consistent=row['prediction']['tuple_consistent'],
                                     action_matches_formal_recommendation=labels['recommendation'] == decision['recommendation']))
        results.append(dict(decision=decision, unresolved_fact_task=task(facts), observations=observations))
    producers = [Path(__file__), ROOT / 'requirements-policy.txt', ROOT / 'formal-recommendation-policy-v1.md']
    producers += sorted((ROOT / 'recommendation_policy_v1').glob('*.py'))
    historical_raw = (HISTORICAL_RUN / 'report.json').read_bytes()
    prep.require(json.loads(historical_raw)['cases'] == results, 'historical decisions or observations changed')
    witness_cases = [r['decision']['case_id'] for r in results
                     if any(s['authority'] == 'source_binding'
                            for s in r['decision']['facts']['ownership']['sources'])]
    return dict(contract='specmetrics.formal-recommendation-replay/v1.1', status='offline_development_replay',
                supersedes_report=dict(artifact=str((HISTORICAL_RUN / 'report.json').relative_to(ROOT)),
                                       sha256=sha(historical_raw)), historical_cases_unchanged=True,
                source_bound_ownership_case_ids=witness_cases,
                source_sha256={str((LIVE / n).relative_to(ROOT)): sha((LIVE / n).read_bytes())
                               for n in ('analysis.json', 'native-report.json', 'responses.jsonl')},
                producer_sha256={str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in producers},
                cases=results, logical_cases=len(results), raw_observations=len(report['rows']),
                provider_requests=0, semantic_accuracy=None, independent_gold=False,
                interpretation='Deterministic compliance with development premises, not improved model accuracy. '
                'Only target-03-cell03 (BDD) uses the source-bound ownership witness. '
                'The other three cases retain development premises and unknown ownership; '
                'baseline model context is unchanged.',
                provider_scoring_enabled=False, metric_effect='none')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    value = prep.encoded(replay())
    if args.write:
        RUN.mkdir(parents=True, exist_ok=False)
        with (RUN / 'report.json').open('xb') as stream:
            stream.write(value)
    else:
        prep.require((RUN / 'report.json').read_bytes() == value, 'formal replay differs')
    print('Offline formal replay: 4 cases, 18 preserved observations, 0 requests; no accuracy claim.')


if __name__ == '__main__':
    main()
