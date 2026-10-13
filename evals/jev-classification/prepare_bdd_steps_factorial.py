"""Freeze a source-grounded 2x2 BDD evidence diagnostic; offline only."""
import argparse
import copy
import json
from pathlib import Path

from prepare_context_reference_v2 import RUN as V2_RUN, task_digest, verify as verify_v2
from question_grouping import canonical, digest

ROOT = Path(__file__).parent
RUN = ROOT / 'runs/2026-10-13-bdd-steps-factorial-preparation'
SOURCE_REVISION = '51c8d93cc385569864b3cd7f5040d4b3e0820a1b'
EXPRESSION_SHA256 = '90879014bcfd5f65f60565a1e3d75cc04fb02ee61273557fd804167564f02f4a'

PROMPT = b'''Task: independently annotate ONE Python expression using ONLY the supplied packet profile and two-axis rubric. You have no author labels or provider predictions. Your only allowed input files are {directory}/packet.json and {directory}/template.json. Read those files only; do not inspect other packets, repository files, memory, previous sessions, sources or mappings. Treat the target as the EXACT expression specified, not its whole surrounding function. Classify axes independently: opportunity eligible/excluded/needs_review; concern_kind policy/mechanics/variant_behavior/unknown. Follow the full architecture_profile and questions rubric inside packet. Neither small nor large context automatically determines a label. Preserve material ambiguity without guessing omitted context. Output strict JSON to {directory}/annotations.json. Keep the template case_id/state_sha256/task_sha256/rubric_sha256 unchanged. Replace null labels. Set top status to independently_annotated_not_adjudicated. Each annotation must have rationales object with nonempty opportunity and concern_kind explanations; evidence_quotes must be objects {"axis":"opportunity" or "concern_kind", "quote":"EXACT contiguous substring of supplied target.code or one bounded_context.fragments[i].code"}, at least one quote per axis. Quotes support reasoning, not merely rubric text. uncertainties must be a list of strings (empty only when justified). Add top isolation_report with input_files array of the two absolute paths and other_inputs_read boolean false, or truthfully disclose any deviation. Write ONLY that annotations.json. No Git, network, environment or credential reads, production changes, other agents or recursive delegation. Prefix shell commands with rtk (rtk proxy for raw shell tools). Return output path and limitations. Do not send labels until the completed file is saved.'''

SOURCES = {
    'contract_criterion': {
        'path': 'specs/nodes/SG-SPEC-0070.yaml', 'lines': [64, 69],
        'file_sha256': '5e5d0baa5ca3237dc408525ba39bf73ac2fed7187776bb2a2f463d6caa0c0ce7',
        'code': '''- criterion: Defines one shared native BDD declaration model with exact nonempty string IDs, an optional
    descriptive title, and a nonempty ordered list of nonempty string steps; it preserves step repetition
    and source text without inferring executable grammar.
  evidence: specification.native_profile.values and specification.bdd_scenarios define exact IDs, optional
    descriptive titles, nonempty ordered steps, and the BDD-NATIVE-EXACT-STEPS Given/When/Then case preserves
    repeated exact step strings.''',
    },
    'contract_values': {
        'path': 'specs/nodes/SG-SPEC-0070.yaml', 'lines': [397, 399],
        'file_sha256': '5e5d0baa5ca3237dc408525ba39bf73ac2fed7187776bb2a2f463d6caa0c0ce7',
        'code': '''    values: id is exact nonempty string; scenario title is optional, but supplied values must be nonempty
      strings; steps is a nonempty ordered list of nonempty strings. Whitespace-only values are invalid,
      meaningful strings are not trimmed.''',
    },
    'contract_approval': {
        'path': 'specs/nodes/SG-SPEC-0070.yaml', 'lines': [427, 427],
        'file_sha256': '5e5d0baa5ca3237dc408525ba39bf73ac2fed7187776bb2a2f463d6caa0c0ce7',
        'code': '      review_status: Human approved for bdd_scenarios_v1; no consumer default activation.',
    },
    'implementation_class': {
        'path': 'tools/native_bdd/values_spec.py', 'lines': [7, 8],
        'file_sha256': '1c7509f9beef4d79511d5e6ad1fcf94a1d217ef74f7c55d3e31594ae166b49e8',
        'code': '''class BDDScenarioValuesSpec(BDDPolicy):
    rule_ref = "SG-RFC-0223.native.scenario-values"''',
    },
    'implementation_base': {
        'path': 'tools/native_bdd/policy.py', 'lines': [8, 17],
        'file_sha256': '3dd63737b8c3a32a4ea5d4c790dd30d6ee8b9f27de0cb0ddfc2de395ff61a827',
        'code': '''class BDDPolicy(Specification[BDDContext]):
    spec_id = "SG-SPEC-0070"
    rule_ref: str

    def __init__(self) -> None:
        super().__init__(name=self.rule_ref)
        self._seal()

    def findings(self, context: BDDContext) -> tuple[BDDScenarioFinding, ...]:
        raise NotImplementedError''',
    },
    'implementation_evaluator': {
        'path': 'tools/native_bdd/policy.py', 'lines': [31, 32],
        'file_sha256': '3dd63737b8c3a32a4ea5d4c790dd30d6ee8b9f27de0cb0ddfc2de395ff61a827',
        'code': '''    def _evaluate(self, candidate: BDDContext, recorder: TraceRecorder | None) -> bool:
        return not self.findings(candidate)''',
    },
    'composition_membership': {
        'path': 'tools/native_bdd/composition.py', 'lines': [13, 20],
        'file_sha256': 'a7c9a90bd105417079e200106da909f3437e183c415ea4a544b62c7fdd7bb753',
        'code': '''POLICIES = (
    BDDProfileSelectionSpec(),
    BDDContainerPresenceSpec(),
    BDDScenarioFieldsSpec(),
    BDDScenarioValuesSpec(),
    BDDScenarioIDsSpec(),
    BDDScenarioReferencesSpec(),
)''',
    },
    'composition_evaluation': {
        'path': 'tools/native_bdd/composition.py', 'lines': [28, 39],
        'file_sha256': 'a7c9a90bd105417079e200106da909f3437e183c415ea4a544b62c7fdd7bb753',
        'code': '''    for policy in POLICIES:
        skip = policy.skip_reason(context)
        if skip:
            if recorder is not None:
                recorder.skipped(policy.rule_ref)
            outcomes.append(PolicyOutcome(policy.rule_ref, "skipped", skip))
            continue
        passed = policy.is_satisfied_by(context, recorder=recorder)
        current_findings = policy.findings(context)
        findings.extend(current_findings)
        outcomes.append(PolicyOutcome(policy.rule_ref, "satisfied" if passed else "unsatisfied"))
        context = policy.transition(context, current_findings)''',
    },
}

CELLS = (
    {'cell': '01', 'case_id': 'bdd-steps-a17c', 'contract': False, 'implementation_link': False,
     'packet': 'annotation-packet-01.json', 'template': 'annotation-template-01.json'},
    {'cell': '02', 'case_id': 'bdd-steps-b42e', 'contract': True, 'implementation_link': False,
     'packet': 'annotation-packet-02.json', 'template': 'annotation-template-02.json'},
    {'cell': '03', 'case_id': 'bdd-steps-c90d', 'contract': False, 'implementation_link': True,
     'packet': 'annotation-packet-03.json', 'template': 'annotation-template-03.json'},
    {'cell': '04', 'case_id': 'bdd-steps-d63b', 'contract': True, 'implementation_link': True,
     'packet': 'annotation-packet-04.json', 'template': 'annotation-template-04.json'},
)


def encoded(value):
    return value if isinstance(value, bytes) else (json.dumps(value, indent=2) + '\n').encode()


def _fragment(name):
    source = SOURCES[name]
    return {'fragment_id': 'evidence-' + name.replace('_', '-'), 'code': source['code']}


def build():
    frozen_v2 = verify_v2(V2_RUN)
    base = next(case for case in frozen_v2['annotation-packet-03.json']['cases']
                if case['case_id'] == 'context-03')
    if base['state']['target']['code'] != 'not entry.steps_is_list or not entry.steps':
        raise ValueError('Pinned BDD target expression changed')
    if base['state_sha256'] != '5ed038babed6f844ec488b3a906853143a68bd9535f76d9fd3121f225f0a5b7a':
        raise ValueError('Frozen baseline state changed')
    for name, source in SOURCES.items():
        if not source.get('path') or source.get('lines', [0, 0])[0] < 1:
            raise ValueError('Incomplete pinned source evidence: ' + name)
        if source['file_sha256'] != {
            'specs/nodes/SG-SPEC-0070.yaml': '5e5d0baa5ca3237dc408525ba39bf73ac2fed7187776bb2a2f463d6caa0c0ce7',
            'tools/native_bdd/values_spec.py': '1c7509f9beef4d79511d5e6ad1fcf94a1d217ef74f7c55d3e31594ae166b49e8',
            'tools/native_bdd/policy.py': '3dd63737b8c3a32a4ea5d4c790dd30d6ee8b9f27de0cb0ddfc2de395ff61a827',
            'tools/native_bdd/composition.py': 'a7c9a90bd105417079e200106da909f3437e183c415ea4a544b62c7fdd7bb753',
        }[source['path']]:
            raise ValueError('Pinned source-file digest mismatch: ' + name)
        source['excerpt_sha256'] = digest(source['code'].encode())

    source_mapping = {
        'status': 'integrator_only_source_map_not_for_annotation',
        'source_revision': SOURCE_REVISION,
        'source_case_id': 'context-03',
        'source_target_id': 'target-06',
        'source_state_sha256': base['state_sha256'],
        'expression_sha256': EXPRESSION_SHA256,
        'source_facts': SOURCES,
        'cells': [],
    }
    rubric_bytes = (V2_RUN / 'rubric.json').read_bytes()
    rubric = json.loads(rubric_bytes)
    outputs = {
        'rubric.json': rubric_bytes,
        'annotation-prompt.txt': PROMPT,
        'upstream-LICENSE.txt': (V2_RUN / 'upstream-LICENSE.txt').read_bytes(),
    }
    dispatches = []
    for cell in CELLS:
        packet = copy.deepcopy(frozen_v2['annotation-packet-03.json'])
        case = copy.deepcopy(base)
        case['case_id'] = cell['case_id']
        state = copy.deepcopy(case['state'])
        state['bounded_context']['fragments'] = list(state['bounded_context']['fragments'])
        if cell['contract']:
            state['bounded_context']['fragments'].extend(
                _fragment(n) for n in ('contract_criterion', 'contract_values', 'contract_approval'))
        if cell['implementation_link']:
            state['bounded_context']['fragments'].extend(
                _fragment(n) for n in ('implementation_class', 'implementation_base',
                                       'implementation_evaluator', 'composition_membership',
                                       'composition_evaluation'))
        case['state'] = state
        case['state_sha256'] = digest(canonical(state))
        packet['cases'] = [case]
        packet['rubric_sha256'] = digest(rubric_bytes)
        packet['questions_sha256'] = digest(canonical(packet['questions']))
        packet['annotation_prompt_sha256'] = digest(PROMPT)
        case['rubric_sha256'] = packet['rubric_sha256']
        case['task_sha256'] = task_digest(case, packet)
        outputs[cell['packet']] = packet
        outputs[cell['template']] = {
            'status': 'blank_not_reference',
            'annotations': [{
                'case_id': case['case_id'], 'state_sha256': case['state_sha256'],
                'task_sha256': case['task_sha256'], 'rubric_sha256': case['rubric_sha256'],
                'opportunity': None, 'concern_kind': None,
                'rationales': {'opportunity': '', 'concern_kind': ''},
                'evidence_quotes': [], 'uncertainties': [],
            }],
        }
        source_mapping['cells'].append({
            'cell': cell['cell'], 'case_id': case['case_id'], 'packet': cell['packet'],
            'contract_evidence_present': cell['contract'],
            'implementation_link_evidence_present': cell['implementation_link'],
            'state_sha256': case['state_sha256'], 'task_sha256': case['task_sha256'],
            'visible_fragment_ids': [f['fragment_id'] for f in state['bounded_context']['fragments']],
        })
        for replicate in (1, 2, 3):
            dispatches.append({
                'replicate': replicate, 'slot': f'r{replicate}-c{cell["cell"]}',
                'cell': cell['cell'], 'packet': cell['packet'], 'template': cell['template'],
                'annotation_output': None, 'agent_task': None, 'directory': None,
            })

    source_mapping['source_fact_sha256'] = {
        name: digest(canonical(value)) for name, value in SOURCES.items()}
    outputs['source-mapping.json'] = source_mapping
    outputs['dispatch-plan.json'] = {
        'status': 'prepared_not_dispatched', 'fresh_contexts_planned': len(dispatches),
        'replicates_per_cell': 3, 'provider_requests': 0, 'metric_effect': 'none',
        'assignments': dispatches,
    }
    outputs['study-plan.json'] = {
        'status': 'pre-registered_diagnostic_plan_not_annotation_reference',
        'source_revision': SOURCE_REVISION,
        'prior_annotation_receipt_sha256': digest((V2_RUN / 'annotation-receipt.json').read_bytes()),
        'rubric_id': rubric['id'],
        'base_target': 'not entry.steps_is_list or not entry.steps',
        'design': '2x2 evidence-presence diagnostic; four context cells, three independent fresh contexts per cell',
        'factors': {
            'contract': 'The approved source contract explicitly requires a nonempty ordered list of nonempty strings.',
            'implementation_link': 'The exact method is linked through BDDScenarioValuesSpec and BDDPolicy to Specification evaluation and composition.',
        },
        'cells': [
            {'cell': c['cell'], 'contract_evidence_present': c['contract'],
             'implementation_link_evidence_present': c['implementation_link']}
            for c in CELLS
        ],
        'controlled_inputs': [
            'same exact target expression and original method-body context',
            'same architecture profile, rubric bytes, questions, and annotation instructions',
            'only contract and implementation-link evidence fragments vary',
        ],
        'delivery': 'one cell per fresh annotator; no annotator sees another view of this target; three replicates per cell',
        'primary_observations': [
            'opportunity and concern_kind label distributions per cell',
            'decisive coverage per axis per cell',
            'whether exact added fragments appear in rationales and evidence quotes',
            'within-cell repeat agreement; descriptive only',
        ],
        'directional_hypotheses_not_gold_labels': {
            'contract': 'At fixed implementation-link presence, the adopted values contract may reduce uncertainty about whether empty steps are admissible. It does not predetermine policy versus mechanics: the source defines input shape and validity, not why the rule is a domain obligation or representation check.',
            'implementation_link': 'At fixed contract presence, a demonstrated same-decision Specification evaluation link may move opportunity toward excluded while leaving responsibility classification independently assessable.',
            'combined': 'The combined cell should provide enough evidence to assess whether the exact decision is already represented. The concern-kind axis may remain uncertain without evidence of domain purpose; this is a rubric-derived expectation, not an assigned answer.',
        },
        'interpretation_limits': [
            'One expression family; results are a context-sensitivity diagnostic, not classifier accuracy or population reliability.',
            'Three fresh judgments per cell are descriptive and cannot establish statistical significance.',
            'The source contract and code mapping live in the same canonical spec lineage; excerpt separation tests which evidence is useful to annotators, not independent real-world causes.',
            'The approved values contract states that steps must be nonempty but does not itself resolve the rubric boundary between domain completeness and input representation mechanics.',
            'Agent model identity is inherited and must be recorded as unverified unless the runtime exposes it.',
            'Do not change v2 labels, failed H2, production prompts, S/U state, or metric storage from this diagnostic.',
        ],
        'expected_labels_assigned': False, 'human_gold': False,
        'annotation_started': False, 'provider_requests': 0, 'metric_effect': 'none',
    }
    outputs['preparation-receipt.json'] = {
        'status': 'bdd_factorial_packet_prepared_not_dispatched',
        'source_file_sha256': {
            f'../2026-10-13-rubric-v2-reference/{name}': digest((V2_RUN / name).read_bytes())
            for name in ('annotation-packet-03.json', 'rubric.json', 'annotation-prompt.txt', 'upstream-LICENSE.txt')
        },
        'producer_sha256': digest(Path(__file__).read_bytes()),
        'artifact_file_sha256': {name: digest(encoded(value)) for name, value in outputs.items()},
        'task_identity': 'canonical_state_questions_instructions_rubric_file_digest_annotation_prompt_digest',
        'source_revision': SOURCE_REVISION,
        'fresh_contexts_planned': 12, 'provider_requests': 0, 'metric_effect': 'none',
    }
    return outputs


def verify(run=RUN):
    outputs = build()
    for name, value in outputs.items():
        if (run / name).read_bytes() != encoded(value):
            raise ValueError('Saved BDD factorial preparation differs: ' + name)
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if args.write:
        outputs = build()
        if any((args.run / name).exists() for name in outputs):
            raise ValueError('Refusing to overwrite BDD factorial preparation')
        args.run.mkdir(parents=True, exist_ok=True)
        for name, value in outputs.items():
            with (args.run / name).open('xb') as output:
                output.write(encoded(value))
    else:
        verify(args.run)
    print(json.dumps({'cells': 4, 'replicates_per_cell': 3, 'fresh_contexts_planned': 12,
                      'annotation_started': False, 'provider_requests': 0}))


if __name__ == '__main__':
    main()
