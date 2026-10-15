"""Prepare/replay four integrator contract examples offline; never dispatch them."""
import argparse
import copy
import json
from pathlib import Path

import pydantic

import intent_first_contract_v4 as rules

ROOT = Path(__file__).resolve().parent
RUN = ROOT / 'runs/2026-10-15-intent-first-v4-contract'
RESULT = ROOT / 'runs/2026-10-14-scope-binding-v3-1-results-astra-high'
MATRIX = ROOT / 'runs/2026-10-15-scope-reference-readiness-v1/matrix.json'
DECISION = ROOT / 'runs/2026-10-15-scope-binding-adjudication-v2/decision.json'
PREPARATION_RECEIPT = ROOT / 'runs/2026-10-14-scope-binding-preparation-v3-1/preparation-receipt.json'
SELECTED = (('target-01', '03'), ('target-02', '01'), ('target-03', '03'), ('target-04', '01'))
PROMPT = rules.PROMPT


def source_case(target, cell):
    rows = json.loads(MATRIX.read_bytes())['rows']
    row = next(r for r in rows if (r['case_id'], r['cell']) == (target, cell))
    slot = row['raw_annotations'][0]['slot']
    path = RESULT / 'delivery' / slot / 'packet.json'
    data = path.read_bytes()
    receipt = json.loads(PREPARATION_RECEIPT.read_bytes())
    if rules.digest(data) != receipt['artifact_file_sha256']['packet-' + slot + '.json']:
        raise ValueError('source packet differs from frozen preparation')
    packet = json.loads(data)
    old = next(c for c in packet['cases'] if c['task_sha256'] == row['task_sha256'])
    if old['case_id'] != target or old['state_sha256'] != row['state_sha256']:
        raise ValueError('source matrix/case identity mismatch')
    return old, path


def make_case(old, cell, contract_sha256):
    state = copy.deepcopy(old['state'])
    state['architecture_profile'] = copy.deepcopy(rules.PROFILE)
    case = {'case_id': old['case_id'] + '-cell' + cell, 'state': state,
            'state_sha256': rules.digest(rules.encoded(state)),
            'scope_binding_sha256': rules.digest(rules.encoded(state['evaluation_scope']))}
    case['task_sha256'] = rules.task_digest(case, contract_sha256)
    return case


def blank(case, contract_sha256):
    return {**{k: case[k] for k in ('case_id', 'task_sha256', 'state_sha256', 'scope_binding_sha256')},
            'contract_id': rules.CONTRACT_ID, 'contract_sha256': contract_sha256,
            'scope_unit': case['state']['evaluation_scope']['unit'],
            'concern_kind': None, 'evidence_confidence': None, 'recommendation': None,
            'basis': None, 'intent_review': {'checked_document_ids': [], 'missing_context': []},
            'rationales': {axis: '' for axis in rules.AXES},
            'evidence_quotes': [], 'uncertainties': []}


def example(case, contract_sha256, index):
    role, confidence, action, basis, reason, witness = (
        ('unknown', 'insufficient', 'formalize', 'formalization_preference',
         'The selected manifest binding checks path shape; its primary contract remains ambiguous without documents. After bounded lookup the profile prefers formalization.',
         ('fragment-04', 'path = _safe_path(row.get("path"))')),
        ('policy', 'supported', 'formalize', 'domain_contract',
         'The selected shared predicate gives outstanding gates priority over ordinary status-based refinement. This domain precedence should be a named rule.',
         ('fragment-01', 'if gate != "none":')),
        ('policy', 'supported', 'reuse_specification', 'existing_specification',
         'The selected invalid-step predicate belongs to BDDScenarioValuesSpec findings/evaluation, including its direct findings binding. Negation does not require a wrapper.',
         ('fragment-02', 'class BDDPolicy(Specification[BDDContext]):')),
        ('mechanics', 'supported', 'use_tool_rules', 'tool_responsibility',
         'The selected shared newline predicate implements serialization formatting. Keep rule management with formatter/linter responsibilities; configured exact enforcement is not established.',
         ('fragment-01', 'rendered += "\\n"')),
    )[index]
    row = blank(case, contract_sha256)
    row.update(concern_kind=role, evidence_confidence=confidence, recommendation=action, basis=basis,
               rationales={'concern_kind': reason, 'evidence_confidence': reason, 'recommendation': reason},
               evidence_quotes=[{'axis': 'concern_kind', 'fragment_id': 'target', 'quote': case['state']['target']['code']},
                                {'axis': 'recommendation', 'fragment_id': witness[0], 'quote': witness[1]}])
    if index == 0:
        row['intent_review']['missing_context'] = ['Intent/proposal/spec documents are not supplied in this evidence view.']
        row['uncertainties'] = ['The primary contract of the entire path predicate at this binding is not established.']
    elif index == 3:
        row['uncertainties'] = ['No configured external rule enforcement is demonstrated.']
    return row


def validate_examples(packet, examples, contract_sha256):
    cases = {c['case_id']: c for c in packet['cases']}
    answers = examples['annotations']
    if len(answers) != len(cases) or {a['case_id'] for a in answers} != set(cases):
        raise ValueError('example case set mismatch')
    return [rules.validate(cases[a['case_id']], a, contract_sha256) for a in answers]


def build():
    contract_bytes = rules.encoded(rules.contract())
    contract_sha256 = rules.digest(contract_bytes)
    cases, bindings = [], []
    inputs = {str(p.relative_to(ROOT)): rules.digest(p.read_bytes()) for p in (MATRIX, DECISION, PREPARATION_RECEIPT)}
    for target, cell in SELECTED:
        old, path = source_case(target, cell)
        case = make_case(old, cell, contract_sha256)
        cases.append(case)
        inputs[str(path.relative_to(ROOT))] = rules.digest(path.read_bytes())
        bindings.append({'case_id': case['case_id'], 'new_task_sha256': case['task_sha256'],
                         'source_packet': str(path.relative_to(ROOT)), 'source_cell': cell,
                         'source_case_id': old['case_id'], 'source_task_sha256': old['task_sha256'],
                         'source_state_sha256': old['state_sha256'],
                         'transformation': 'target/context/evaluation_scope unchanged; architecture_profile, state/task hashes and contract version changed'})
    packet = {'contract_id': rules.CONTRACT_ID, 'contract_sha256': contract_sha256, 'cases': cases}
    examples = {'status': 'integrator_examples_after_human_guidance_not_model_outputs_not_gold',
                'annotations': [example(c, contract_sha256, i) for i, c in enumerate(cases)]}
    validate_examples(packet, examples, contract_sha256)
    files = {'contract.json': contract_bytes, 'packet.json': rules.encoded(packet),
             'template.json': rules.encoded({'status': 'blank_not_reference', 'annotations': [blank(c, contract_sha256) for c in cases]}),
             'prompt.txt': PROMPT.encode(), 'source-bindings.json': rules.encoded(bindings),
             'integrator-examples.json': rules.encoded(examples),
             'README.md': (
                 '# Intent-first v4: offline contract examples\n\n'
                 'Four source-grounded development examples, not model answers or a scoring reference.\n'
                 'The examples apply the [human clarification](../2026-10-15-scope-binding-adjudication-v2/README.md).\n'
                 'See the [contract guide](../../intent-first-evaluation-v4.md) for semantics and limits.\n\n'
                 'Inspect `integrator-examples.json` to see the three independent fields: concern kind,\n'
                 'evidence confidence and recommendation. The no-document manifest example recommends\n'
                 'formalization while keeping unknown role / insufficient support. Gate precedence is\n'
                 'formalize; BDD is reuse_specification; newline is use_tool_rules.\n\n'
                 'Only packet/contract/template and prompt are prospective annotator inputs. Source\n'
                 'bindings, integrator examples, receipts and this guide are integrator-only. No\n'
                 'handoff, isolated execution, annotation dispatch or provider wire adapter is prepared.\n'
                 'The four examples were previously discussed and cannot be an unseen holdout.\n'
                 'No new model contexts/provider requests; production S/U and frozen history unchanged.\n'
                 'Structural/identity/quote validation does not establish semantic correctness.\n'
             ).encode()}
    receipt = {'schema_version': '4.0', 'status': 'offline_contract_examples_not_dispatched',
               'producer_file_sha256': {n: rules.digest((ROOT / n).read_bytes()) for n in
                                        ('intent_first_contract_v4.py', 'prepare_intent_first_v4.py')},
               'input_file_sha256': inputs, 'pydantic_version': pydantic.__version__,
               'artifact_file_sha256': {n: rules.digest(v) for n, v in files.items()},
               'examples': 4, 'dispatch_ready': False, 'human_gold': False,
               'provider_scoring_enabled': False, 'new_model_contexts': 0,
               'provider_requests': 0, 'metric_effect': 'none'}
    files['preparation-receipt.json'] = rules.encoded(receipt)
    files['SHA256SUMS'] = ''.join(rules.digest(v) + '  ' + n + '\n' for n, v in sorted(files.items())).encode()
    return files


def verify(run=RUN):
    files = build()
    if {p.name for p in run.iterdir()} != set(files):
        raise ValueError('v4 preparation file set differs')
    for name, value in files.items():
        if (run / name).read_bytes() != value:
            raise ValueError('v4 preparation bytes differ: ' + name)
    return files


def write(run):
    files = build()
    run.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        with (run / name).open('xb') as stream:
            stream.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if args.write:
        write(args.run)
    else:
        verify(args.run)
    print(json.dumps({'status': 'offline_contract_examples_not_dispatched', 'examples': 4,
                      'provider_requests': 0, 'semantic_correctness_verified': False}))


if __name__ == '__main__':
    main()
