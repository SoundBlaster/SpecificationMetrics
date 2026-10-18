"""Future portable, counterbalanced repeatability preparation; no dispatch."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

import paired_reference_repeatability_v1 as historical
from paired_blind_reference_v1 import PROMPT_END, PROMPT_HEADER
from coreinfra_retry_run import decode, sha
from retrieval_index_v1.source import encoded

CONTRACT = 'specmetrics.paired-reference-repeatability/v2'
ROOT = historical.ROOT


def prompt(task):
    paths = ['evals/jev-classification/' + name for name in sorted(task['input_sha256'])]
    return '\n'.join([PROMPT_HEADER + ' Paths are relative to the repository root.', *paths, PROMPT_END]) + '\n'


def build_plan():
    old = historical.build_plan()
    cases = sorted({t['case_id'] for t in old['tasks']})
    lookup = {(t['repeat'], t['case_id'], t['arm']): t for t in old['tasks']}
    tasks = []
    for repeat in range(1, historical.REPEATS + 1):
        order = list(dict.fromkeys(t['case_id'] for t in old['tasks'] if t['repeat'] == repeat))
        for case in order:
            arms = ('baseline', 'retrieval') if (cases.index(case) + repeat) % 2 else ('retrieval', 'baseline')
            for arm in arms:
                task = deepcopy(lookup[repeat, case, arm])
                task['task_id'] = 'repeat-v2-' + sha(f'{CONTRACT}:{repeat}:{task["view_id"]}'.encode())[:16]
                task['prompt_source'] = 'prompts/' + task['task_id'] + '.txt'
                task['prompt_sha256'] = sha(prompt(task).encode())
                tasks.append(task)
    return dict(old, contract=CONTRACT, supersedes_preparation=historical.CONTRACT,
        tasks=tasks, prompt_working_directory='repository_root',
        ordering='stable_case_index_plus_repeat_controls_first_arm_independently_of_case_shuffle',
        dispatch_authorized=False, historical_run_reinterpreted=False,
        historical_order_limitation='v1_R03_baseline_first_and_R04_retrieval_first_in_all_blocks')


def producers():
    return dict(historical.producers(), **{Path(__file__).name: sha(Path(__file__).read_bytes())})


def freeze(output):
    plan = build_plan()
    output.mkdir(exist_ok=False)
    (output / 'prompts').mkdir()
    (output / 'plan.json').write_text(encoded(plan) + '\n')
    for task in plan['tasks']:
        (output / task['prompt_source']).write_text(prompt(task))
    files = {str(p.relative_to(output)): sha(p.read_bytes()) for p in output.rglob('*') if p.is_file()}
    (output / 'receipt.json').write_text(encoded(dict(contract=CONTRACT,
        file_sha256=files, producer_sha256=producers())) + '\n')
    return verify(output)


def verify(output):
    plan = build_plan()
    expected = {'plan.json': (encoded(plan) + '\n').encode()}
    expected.update({t['prompt_source']: prompt(t).encode() for t in plan['tasks']})
    actual = {str(p.relative_to(output)): p.read_bytes() for p in output.rglob('*')
              if p.is_file() and p != output / 'receipt.json'}
    if actual != expected or decode((output / 'receipt.json').read_bytes()) != dict(contract=CONTRACT,
            file_sha256={name: sha(raw) for name, raw in expected.items()}, producer_sha256=producers()):
        raise ValueError('portable repeatability preparation differs')
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--freeze', type=Path)
    group.add_argument('--verify', type=Path)
    args = parser.parse_args()
    plan = freeze(args.freeze) if args.freeze else verify(args.verify)
    print(json.dumps(dict(contract=CONTRACT, tasks=len(plan['tasks']), dispatch_authorized=False)))
