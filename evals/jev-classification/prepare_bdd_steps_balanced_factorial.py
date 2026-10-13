"""Freeze a balanced, source-grounded 2x2 BDD evidence diagnostic; offline only."""
import argparse
import copy
import json
from pathlib import Path

import prepare_bdd_steps_factorial as initial
from prepare_context_reference_v2 import task_digest, verify as verify_v2
from question_grouping import canonical, digest

ROOT = Path(__file__).parent
RUN = ROOT / 'runs/2026-10-13-bdd-steps-balanced-factorial-preparation'
V2_RUN = initial.V2_RUN
SOURCE_REVISION = initial.SOURCE_REVISION

PROMPT = b'''Task: independently annotate every exact Python expression in ONE packet. Each packet has four distinct target expressions from two BDD SpecificationCore policy classes. A case is an independent annotation unit: classify it using only that case's target and bounded_context, and do not transfer evidence from another case. You have no author labels or provider predictions. Your only allowed input files are {directory}/packet.json and {directory}/template.json. Read those files only; do not inspect other packets, repository files, memory, previous sessions, sources or mappings. Treat each target as the EXACT expression specified, not its whole surrounding method. Classify axes independently: opportunity eligible/excluded/needs_review; concern_kind policy/mechanics/variant_behavior/unknown. Follow the full architecture_profile and questions rubric inside packet. Neither small nor large context automatically determines a label. Preserve material ambiguity without guessing omitted context. Output strict JSON to {directory}/annotations.json. Keep every template case_id/state_sha256/task_sha256/rubric_sha256 unchanged. Replace null labels. Each annotation must have rationales object with nonempty opportunity and concern_kind explanations; evidence_quotes must be objects {"axis":"opportunity" or "concern_kind", "quote":"EXACT contiguous substring of this case's supplied target.code or bounded_context.fragments[i].code"}, at least one quote per axis. Quotes support reasoning, not merely rubric text. uncertainties must be a list of strings (empty only when justified). Set top status to independently_annotated_not_adjudicated. Add top isolation_report with input_files array of the two absolute paths and other_inputs_read boolean false, or truthfully disclose any deviation. Write ONLY that annotations.json. No Git, network, environment or credential reads, production changes, other agents or recursive delegation. Prefix shell commands with rtk (rtk proxy for raw shell tools). Return output path and limitations. Do not send labels until the completed file is saved.'''

CONDITIONS = (
    {'cell': '01', 'contract': False, 'implementation_link': False},
    {'cell': '02', 'contract': True, 'implementation_link': False},
    {'cell': '03', 'contract': False, 'implementation_link': True},
    {'cell': '04', 'contract': True, 'implementation_link': True},
)

VALUES_METHOD = '''    def findings(self, context: BDDContext):
        findings = []
        for index, entry in enumerate(context.entries):
            if not entry.is_mapping:
                continue
            path = f"specification.bdd_scenarios[{index}]"
            if not entry.id.valid:
                findings.append(issue("invalid_value", path + ".id"))
            if not entry.steps_is_list or not entry.steps:
                findings.append(issue("invalid_value", path + ".steps"))
            else:
                findings.extend(
                    issue("invalid_value", f"{path}.steps[{i}]")
                    for i, step in enumerate(entry.steps)
                    if not step.valid
                )
        return tuple(findings)'''

FIELDS_METHOD = '''    def findings(self, context: BDDContext):
        findings = []
        for index, entry in enumerate(context.entries):
            path = f"specification.bdd_scenarios[{index}]"
            if not entry.is_mapping:
                findings.append(issue("invalid_entry", path))
                continue
            if entry.title_supplied and not entry.title.valid:
                findings.append(issue("invalid_value", path + ".scenario"))
            findings.extend(
                issue("unsupported_field", path + "." + key) for key in entry.unknown_fields
            )
        return tuple(findings)'''

VALUES_CLASS = '''class BDDScenarioValuesSpec(BDDPolicy):
    rule_ref = "SG-RFC-0223.native.scenario-values"

    def skip_reason(self, context: BDDContext) -> str | None:
        return super().skip_reason(context) or entry_skip(context)

    def findings(self, context: BDDContext):
        findings = []
        for index, entry in enumerate(context.entries):
            if not entry.is_mapping:
                continue
            path = f"specification.bdd_scenarios[{index}]"
            if not entry.id.valid:
                findings.append(issue("invalid_value", path + ".id"))
            if not entry.steps_is_list or not entry.steps:
                findings.append(issue("invalid_value", path + ".steps"))
            else:
                findings.extend(
                    issue("invalid_value", f"{path}.steps[{i}]")
                    for i, step in enumerate(entry.steps)
                    if not step.valid
                )
        return tuple(findings)'''

FIELDS_CLASS = '''class BDDScenarioFieldsSpec(BDDPolicy):
    rule_ref = "SG-RFC-0223.native.scenario-fields"

    def skip_reason(self, context: BDDContext) -> str | None:
        return super().skip_reason(context) or entry_skip(context)

    def findings(self, context: BDDContext):
        findings = []
        for index, entry in enumerate(context.entries):
            path = f"specification.bdd_scenarios[{index}]"
            if not entry.is_mapping:
                findings.append(issue("invalid_entry", path))
                continue
            if entry.title_supplied and not entry.title.valid:
                findings.append(issue("invalid_value", path + ".scenario"))
            findings.extend(
                issue("unsupported_field", path + "." + key) for key in entry.unknown_fields
            )
        return tuple(findings)'''

SOURCES = {name: dict(value) for name, value in initial.SOURCES.items()
           if name != 'implementation_class'}
SOURCES['implementation_values_class'] = {
    'path': 'tools/native_bdd/values_spec.py', 'lines': [7, 29],
    'file_sha256': '1c7509f9beef4d79511d5e6ad1fcf94a1d217ef74f7c55d3e31594ae166b49e8',
    'code': VALUES_CLASS,
}
SOURCES['implementation_fields_class'] = {
    'path': 'tools/native_bdd/fields_spec.py', 'lines': [7, 25],
    'file_sha256': 'e7b8600deeebb0f68284213a8fd8894cb9f4f52c53d359b8112f968c72950f59',
    'code': FIELDS_CLASS,
}

TARGETS = (
    {'case_id': 'bdd-values-steps-list', 'code': 'not entry.steps_is_list or not entry.steps',
     'syntax_kind': 'BoolOp', 'class_fact': 'implementation_values_class',
     'method_only': VALUES_METHOD},
    {'case_id': 'bdd-values-id', 'code': 'not entry.id.valid', 'syntax_kind': 'UnaryOp',
     'class_fact': 'implementation_values_class', 'method_only': VALUES_METHOD},
    {'case_id': 'bdd-values-step-item', 'code': 'not step.valid', 'syntax_kind': 'UnaryOp',
     'class_fact': 'implementation_values_class', 'method_only': VALUES_METHOD},
    {'case_id': 'bdd-fields-optional-title',
     'code': 'entry.title_supplied and not entry.title.valid', 'syntax_kind': 'BoolOp',
     'class_fact': 'implementation_fields_class', 'method_only': FIELDS_METHOD},
)


def encoded(value):
    return value if isinstance(value, bytes) else (json.dumps(value, indent=2) + '\n').encode()


def _fragment(name):
    source = SOURCES[name]
    return {'fragment_id': 'evidence-' + name.replace('_', '-'), 'code': source['code']}


def _case(base, target, condition, packet):
    case = copy.deepcopy(base)
    case['case_id'] = target['case_id']
    state = copy.deepcopy(case['state'])
    state['target']['code'] = target['code']
    state['target']['syntax_kind'] = target['syntax_kind']
    state['target']['scope'] = 'exact expression only'
    method = target['method_only']
    class_source = SOURCES[target['class_fact']]['code']
    if condition['implementation_link']:
        method = class_source
    state['bounded_context']['fragments'] = [
        {'fragment_id': 'target-method-context', 'code': method}
    ]
    if condition['contract']:
        state['bounded_context']['fragments'].extend(
            _fragment(name) for name in ('contract_criterion', 'contract_values', 'contract_approval'))
    if condition['implementation_link']:
        state['bounded_context']['fragments'].extend(
            _fragment(name) for name in ('implementation_base', 'implementation_evaluator',
                                         'composition_membership', 'composition_evaluation'))
    case['state'] = state
    case['state_sha256'] = digest(canonical(state))
    case['rubric_sha256'] = packet['rubric_sha256']
    case['task_sha256'] = task_digest(case, packet)
    return case


def build():
    frozen_v2 = verify_v2(V2_RUN)
    base = next(case for case in frozen_v2['annotation-packet-03.json']['cases']
                if case['case_id'] == 'context-03')
    if base['state_sha256'] != '5ed038babed6f844ec488b3a906853143a68bd9535f76d9fd3121f225f0a5b7a':
        raise ValueError('Frozen baseline state changed')
    if base['state']['target']['code'] != TARGETS[0]['code']:
        raise ValueError('Pinned BDD steps target changed')

    expected_files = {
        'specs/nodes/SG-SPEC-0070.yaml': '5e5d0baa5ca3237dc408525ba39bf73ac2fed7187776bb2a2f463d6caa0c0ce7',
        'tools/native_bdd/values_spec.py': '1c7509f9beef4d79511d5e6ad1fcf94a1d217ef74f7c55d3e31594ae166b49e8',
        'tools/native_bdd/fields_spec.py': 'e7b8600deeebb0f68284213a8fd8894cb9f4f52c53d359b8112f968c72950f59',
        'tools/native_bdd/policy.py': '3dd63737b8c3a32a4ea5d4c790dd30d6ee8b9f27de0cb0ddfc2de395ff61a827',
        'tools/native_bdd/composition.py': 'a7c9a90bd105417079e200106da909f3437e183c415ea4a544b62c7fdd7bb753',
    }
    for name, source in SOURCES.items():
        if not source.get('path') or source.get('lines', [0, 0])[0] < 1:
            raise ValueError('Incomplete pinned source evidence: ' + name)
        if source['file_sha256'] != expected_files[source['path']]:
            raise ValueError('Pinned source-file digest mismatch: ' + name)
        source['excerpt_sha256'] = digest(source['code'].encode())

    source_mapping = {
        'status': 'integrator_only_source_map_not_for_annotation',
        'source_revision': SOURCE_REVISION,
        'prior_source_case_id': 'context-03',
        'prior_source_state_sha256': base['state_sha256'],
        'source_facts': SOURCES,
        'targets': [
            {'case_id': target['case_id'], 'code': target['code'],
             'syntax_kind': target['syntax_kind'], 'class_fact': target['class_fact']}
            for target in TARGETS
        ],
        'conditions': [
            {'cell': condition['cell'], 'contract_evidence_present': condition['contract'],
             'implementation_link_evidence_present': condition['implementation_link']}
            for condition in CONDITIONS
        ],
        'assignments': [],
    }
    rubric_bytes = (V2_RUN / 'rubric.json').read_bytes()
    frozen_packet = frozen_v2['annotation-packet-03.json']
    outputs = {
        'rubric.json': rubric_bytes,
        'annotation-prompt.txt': PROMPT,
        'upstream-LICENSE.txt': (V2_RUN / 'upstream-LICENSE.txt').read_bytes(),
    }
    assignments = []
    target_cell_counts = {target['case_id']: {c['cell']: 0 for c in CONDITIONS}
                          for target in TARGETS}
    position_cell_counts = {position: {c['cell']: 0 for c in CONDITIONS} for position in range(4)}

    for annotator_index in range(12):
        slot = f'annotator-{annotator_index + 1:02d}'
        condition_offset = annotator_index // 3
        order_offset = annotator_index % 3
        packet = copy.deepcopy(frozen_packet)
        packet['cases'] = []
        packet['rubric_sha256'] = digest(rubric_bytes)
        packet['questions_sha256'] = digest(canonical(packet['questions']))
        packet['annotation_prompt_sha256'] = digest(PROMPT)
        target_assignments = []
        for position in range(4):
            target_index = (position + order_offset) % 4
            target = TARGETS[target_index]
            condition = CONDITIONS[(target_index + condition_offset) % 4]
            case = _case(base, target, condition, packet)
            packet['cases'].append(case)
            target_assignments.append({
                'case_id': target['case_id'], 'cell': condition['cell'], 'position': position + 1,
                'state_sha256': case['state_sha256'], 'task_sha256': case['task_sha256'],
            })
            target_cell_counts[target['case_id']][condition['cell']] += 1
            position_cell_counts[position][condition['cell']] += 1
        packet_name = f'annotation-packet-{slot}.json'
        template_name = f'annotation-template-{slot}.json'
        outputs[packet_name] = packet
        outputs[template_name] = {
            'status': 'blank_not_reference',
            'annotations': [{
                'case_id': case['case_id'], 'state_sha256': case['state_sha256'],
                'task_sha256': case['task_sha256'], 'rubric_sha256': case['rubric_sha256'],
                'opportunity': None, 'concern_kind': None,
                'rationales': {'opportunity': '', 'concern_kind': ''},
                'evidence_quotes': [], 'uncertainties': [],
            } for case in packet['cases']],
        }
        assignment = {
            'slot': slot, 'packet': packet_name, 'template': template_name,
            'annotation_output': None, 'agent_task': None, 'directory': None,
            'target_cell_assignments': target_assignments,
        }
        assignments.append(assignment)
        source_mapping['assignments'].append(assignment)

    if any(count != 3 for target in target_cell_counts.values() for count in target.values()):
        raise ValueError('Each target-condition cell must receive three independent contexts')
    if any(count != 3 for position in position_cell_counts.values() for count in position.values()):
        raise ValueError('Condition must be balanced across packet positions')

    source_mapping['source_fact_sha256'] = {
        name: digest(canonical(value)) for name, value in SOURCES.items()}
    outputs['source-mapping.json'] = source_mapping
    outputs['dispatch-plan.json'] = {
        'status': 'prepared_not_dispatched', 'fresh_contexts_planned': 12,
        'targets_per_context': 4, 'case_annotations_planned': 48,
        'conditions_per_context': 4, 'contexts_per_target_condition': 3,
        'provider_requests': 0, 'metric_effect': 'none', 'assignments': assignments,
    }
    outputs['study-plan.json'] = {
        'status': 'pre-registered_balanced_diagnostic_plan_not_annotation_reference',
        'source_revision': SOURCE_REVISION,
        'prior_annotation_receipt_sha256': digest((V2_RUN / 'annotation-receipt.json').read_bytes()),
        'rubric_id': json.loads(rubric_bytes)['id'],
        'design': '2x2 evidence-presence diagnostic; four related decision sites, twelve fresh contexts; each context sees every condition once and one view of each site',
        'target_family': 'Four exact predicates from BDDScenarioValuesSpec.findings and BDDScenarioFieldsSpec.findings, both linked to SG-SPEC-0070.',
        'factors': {
            'contract': 'The approved source contract defines exact nonempty IDs, optional supplied titles, and nonempty ordered steps of nonempty strings.',
            'implementation_link': 'The target-containing contiguous class/method excerpt, Specification base, evaluator and composition registration are supplied.',
        },
        'conditions': [
            {'cell': c['cell'], 'contract_evidence_present': c['contract'],
             'implementation_link_evidence_present': c['implementation_link']}
            for c in CONDITIONS
        ],
        'target_cases': [
            {'case_id': t['case_id'], 'expression': t['code'], 'syntax_kind': t['syntax_kind']}
            for t in TARGETS
        ],
        'controlled_inputs': [
            'same target expression and target-specific method body across the four evidence cells',
            'same architecture profile, rubric bytes, questions, and annotation instructions',
            'only adopted contract and explicit Specification linkage evidence vary within each target',
        ],
        'assignment_balance': {
            'per_context': 'four distinct targets and exactly one case from each evidence cell',
            'per_target_cell': 'three fresh contexts',
            'presentation_order': 'each cell appears three times at each packet position',
            'same_target_views': 'no annotator receives multiple evidence cells for the same target',
        },
        'primary_observations': [
            'opportunity and concern-kind label distributions by target and evidence cell',
            'decisive coverage per axis by target and cell',
            'whether exact added fragments appear in rationales and evidence quotes',
            'within-cell repeat agreement, descriptive only',
        ],
        'directional_hypotheses_not_gold_labels': {
            'contract': 'At fixed implementation-link presence, the adopted contract may reduce uncertainty about validity for the corresponding target. It does not predetermine policy versus mechanics.',
            'implementation_link': 'At fixed contract presence, explicit class, Specification and composition evidence may move opportunity toward excluded while leaving concern kind independently assessable.',
            'combined': 'The combined cell may clarify existing representation; concern kind can remain uncertain where domain purpose is not specified.',
        },
        'interpretation_limits': [
            'Four related decision sites from two classes under one Specification lineage are not an independent sample of the codebase.',
            'Three fresh contexts per target-cell support descriptive comparison, not significance or classifier accuracy claims.',
            'Each context sees four related cases; case-local instructions and balanced order reduce but cannot eliminate cross-case carryover.',
            'The approved contract defines validity but does not itself settle the policy-versus-mechanics boundary.',
            'Agent model identity is inherited and must be recorded as unverified unless exposed by the runtime.',
            'Do not change v2 labels, failed H2, production prompts, S/U state, or metric storage from this diagnostic.',
        ],
        'expected_labels_assigned': False, 'human_gold': False,
        'annotation_started': False, 'provider_requests': 0, 'metric_effect': 'none',
    }
    outputs['preparation-receipt.json'] = {
        'status': 'bdd_balanced_factorial_packet_prepared_not_dispatched',
        'source_file_sha256': {
            f'../2026-10-13-rubric-v2-reference/{name}': digest((V2_RUN / name).read_bytes())
            for name in ('annotation-packet-03.json', 'rubric.json', 'annotation-prompt.txt', 'upstream-LICENSE.txt')
        },
        'producer_sha256': digest(Path(__file__).read_bytes()),
        'artifact_file_sha256': {name: digest(encoded(value)) for name, value in outputs.items()},
        'task_identity': 'per_case_state_questions_instructions_rubric_file_digest_annotation_prompt_digest',
        'source_revision': SOURCE_REVISION, 'fresh_contexts_planned': 12,
        'distinct_targets': 4, 'case_annotations_planned': 48,
        'provider_requests': 0, 'metric_effect': 'none',
    }
    return outputs


def verify(run=RUN):
    outputs = build()
    for name, value in outputs.items():
        if (run / name).read_bytes() != encoded(value):
            raise ValueError('Saved balanced BDD preparation differs: ' + name)
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if args.write:
        outputs = build()
        if any((args.run / name).exists() for name in outputs):
            raise ValueError('Refusing to overwrite balanced BDD preparation')
        args.run.mkdir(parents=True, exist_ok=True)
        for name, value in outputs.items():
            with (args.run / name).open('xb') as output:
                output.write(encoded(value))
    else:
        verify(args.run)
    print(json.dumps({'targets': 4, 'conditions': 4, 'fresh_contexts_planned': 12,
                      'case_annotations_planned': 48, 'annotation_started': False,
                      'provider_requests': 0}))


if __name__ == '__main__':
    main()
