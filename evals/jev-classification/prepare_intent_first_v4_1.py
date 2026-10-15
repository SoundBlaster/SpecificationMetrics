"""Replay preserved v4 and prepare corrected v4.1 without rewriting history."""
import argparse
import json
from pathlib import Path

import pydantic

import intent_first_contract_v4_1 as rules
import prepare_intent_first_v4 as previous

ROOT = previous.ROOT
RUN = ROOT / 'runs/2026-10-15-intent-first-v4-1-contract'


def build():
    old = previous.verify()
    contract_bytes = rules.encoded(rules.contract())
    contract_hash = rules.digest(contract_bytes)
    packet, template, examples = [json.loads(old[n]) for n in
                                  ('packet.json', 'template.json', 'integrator-examples.json')]
    template.pop('status')  # Scaffold has the exact response envelope; receipt records its blank state.
    bindings = []
    for case, blank, example in zip(packet['cases'], template['annotations'], examples['annotations']):
        prior_task = case['task_sha256']
        case['task_sha256'] = rules.task_digest(case, contract_hash)
        for row in (blank, example):
            row.update(contract_id=rules.CONTRACT_ID, contract_sha256=contract_hash,
                       task_sha256=case['task_sha256'])
        bindings.append({'case_id': case['case_id'], 'prior_contract_id': previous.rules.CONTRACT_ID,
                         'prior_task_sha256': prior_task, 'task_sha256': case['task_sha256'],
                         'state_sha256': case['state_sha256'], 'scope_binding_sha256': case['scope_binding_sha256'],
                         'transformation': 'contract/task identity changed; state, profile, scope, source code and example labels/actions preserved'})
    packet.update(contract_id=rules.CONTRACT_ID, contract_sha256=contract_hash)
    rules.validate_response(packet, {'annotations': examples['annotations']}, contract_hash)
    files = {'contract.json': contract_bytes, 'packet.json': rules.encoded(packet),
             'template.json': rules.encoded(template), 'prompt.txt': old['prompt.txt'],
             'integrator-examples.json': rules.encoded(examples), 'source-bindings.json': rules.encoded(bindings),
             'README.md': (
                 '# Intent-first v4.1: consistency repair\n\n'
                 'Supersedes [preserved v4](../2026-10-15-intent-first-v4-contract/README.md) for future tasks.\n'
                 'The four integrator examples keep their source, state, scope, profile and labels/actions.\n'
                 'Contract/task identities change; the template drops integrator-only status metadata.\n'
                 'No new model outputs or scoring reference.\n\n'
                 '`keep_procedural` now requires `mechanics / supported`. Policy, unknown or limited\n'
                 'support cannot justify this recommendation. The output schema is the strict\n'
                 '`{"annotations": [...]}` response used by prompt/template/consumer.\n'
                 '`formalization_preference` means uncertainty in primary role; supported domain\n'
                 'rules use `domain_contract` even if implementation details remain undecided.\n\n'
                 'See [contract guide](../../intent-first-evaluation-v4.md) and\n'
                 '[failure diagnosis](../../failure-learning.md#intent-first-v41-consistency-repair-2026-10-15).\n'
                 'Only packet, contract, template and prompt are prospective annotator inputs.\n'
                 'Integrator examples/source mappings are not annotator inputs. Dispatch remains\n'
                 'unprepared; no provider requests, classifier/SU changes or semantic accuracy claims.\n'
             ).encode()}
    receipt = {'schema_version': '4.1', 'status': 'offline_contract_examples_not_dispatched',
               'producer_file_sha256': {n: rules.digest((ROOT / n).read_bytes()) for n in
                                        ('intent_first_contract_v4_1.py', 'prepare_intent_first_v4_1.py')},
               'input_file_sha256': {str((previous.RUN / n).relative_to(ROOT)): rules.digest(v) for n, v in old.items()},
               'pydantic_version': pydantic.__version__,
               'artifact_file_sha256': {n: rules.digest(v) for n, v in files.items()},
               'supersedes': str(previous.RUN.relative_to(ROOT)), 'examples': 4,
               'dispatch_ready': False, 'human_gold': False, 'provider_scoring_enabled': False,
               'new_model_contexts': 0, 'provider_requests': 0, 'metric_effect': 'none'}
    files['preparation-receipt.json'] = rules.encoded(receipt)
    files['SHA256SUMS'] = ''.join(rules.digest(v) + '  ' + n + '\n' for n, v in sorted(files.items())).encode()
    return files


def verify(run=RUN):
    files = build()
    if {p.name for p in run.iterdir()} != set(files):
        raise ValueError('v4.1 preparation file set differs')
    for name, value in files.items():
        if (run / name).read_bytes() != value:
            raise ValueError('v4.1 preparation bytes differ: ' + name)
    return files


def write(run):
    files = build()
    run.mkdir(parents=True, exist_ok=False)
    for name, value in files.items():
        with (run / name).open('xb') as stream:
            stream.write(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    write(args.run) if args.write else verify(args.run)
    print(json.dumps({'status': 'offline_contract_examples_not_dispatched', 'version': '4.1',
                      'examples': 4, 'provider_requests': 0, 'semantic_correctness_verified': False}))


if __name__ == '__main__':
    main()
