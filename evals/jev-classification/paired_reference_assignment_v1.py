"""Freeze an integrator-only balanced annotation handoff without dispatching it."""
import argparse
import json
from pathlib import Path

import coreinfra_retry_run as transport
from paired_retrieval_study_v1 import source_digests, verify as verify_preparation
from retrieval_index_v1.source import encoded

CONTRACT = 'specmetrics.paired-reference-assignment/v1'
FAMILIES = dict(R01='workspace_allocation', R02='subject_source_write',
                R03='subject_source_write', R04='workspace_paths')
# Slots identify distinct real annotators, including memory shared across sessions.
# Each receives baseline first, then a different dependency family's retrieval.
ASSIGNMENTS = (
    ('A', 'R01', 'R02'), ('B', 'R02', 'R01'),
    ('C', 'R03', 'R04'), ('D', 'R04', 'R03'),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_assignments(slots):
    require(len(slots) == 4 and {s['annotator_slot'] for s in slots} == set('ABCD'),
            'expected four distinct annotator slots')
    seen = set()
    for slot in slots:
        tasks = slot['tasks']
        require(len(tasks) == 2 and [t['arm'] for t in tasks] == ['baseline', 'retrieval'],
                'every annotator needs one baseline first and one retrieval second')
        require(all(t['case_id'] in FAMILIES and t['family'] == FAMILIES[t['case_id']] for t in tasks),
                'unknown or substituted dependency family')
        require(len({t['family'] for t in tasks}) == 2,
                'same target or shared dependency family assigned to one annotator')
        require(tasks[0]['after_annotation_sealed'] is None
                and tasks[1]['after_annotation_sealed'] == tasks[0]['task_id'],
                'retrieval requires the earlier baseline annotation to be sealed')
        for task in tasks:
            identity = (task['case_id'], task['arm'])
            require(identity not in seen, 'duplicate evidence view')
            seen.add(identity)
    require(seen == {(case, arm) for case in FAMILIES for arm in ('baseline', 'retrieval')},
            'missing evidence view')


def definitions(state):
    result = set()
    for document in [state['target'], *state['retrieved_context']]:
        result.add(document['id'])
        result.update(document['source']['path'] + '::' + h['symbol'] for h in document['helpers'])
    return result


def build_plan(preparation):
    verify_preparation(preparation)
    reference = transport.decode((preparation / 'reference-index.json').read_bytes())
    views = {(v['case_id'], v['arm']): v['view_id'] for v in reference['views']}
    require(set(views) == {(case, arm) for case in FAMILIES for arm in ('baseline', 'retrieval')},
            'assignment v1 requires the original four-case cohort')
    slots = []
    for slot, baseline_case, retrieval_case in ASSIGNMENTS:
        tasks = []
        states = []
        for position, (case, arm) in enumerate(((baseline_case, 'baseline'), (retrieval_case, 'retrieval'))):
            view = 'blind/' + views[case, arm]
            names = [view + '/packet.json', view + '/annotation-template.json']
            state = transport.decode((preparation / names[0]).read_bytes())['state']
            states.append(state)
            tasks.append(dict(task_id=slot + str(position + 1), case_id=case, arm=arm,
                view_id=views[case, arm], family=FAMILIES[case],
                files={n: transport.sha((preparation / n).read_bytes()) for n in names},
                after_annotation_sealed=None if position == 0 else slot + '1'))
        baseline_full = transport.decode((preparation / baseline_case / 'retrieval/packet.json').read_bytes())['state']
        withheld = definitions(baseline_full) - definitions(states[0])
        slots.append(dict(annotator_slot=slot, tasks=tasks,
            leakage_audit=dict(withheld_baseline_definitions_present_in_later_view=sorted(
                withheld & definitions(states[1])),
                prevention='seal_baseline_before_releasing_later_view',
                coverage='supplied_declarations_and_helpers_only_not_general_dependency_analysis')))
    validate_assignments(slots)
    return dict(contract=CONTRACT, status='prepared_not_dispatched', visibility='integrator_only',
        preparation_manifest_sha256=transport.sha((preparation / 'manifest.json').read_bytes()),
        preparation_receipt_sha256=transport.sha((preparation / 'study-receipt.json').read_bytes()),
        annotator_binding='pending_four_distinct_unexposed_actual_identities',
        isolation='one_packet_per_fresh_context_with_identity_memory_tracked_across_contexts',
        order_limit='baseline_first_prevents_withheld_evidence_carryover_but_does_not_estimate_order_effects',
        independent_reference_status='pending_blind_annotation_and_adjudication', slots=slots,
        hosted_requests=0, dispatch_authorized=False)


def validate_roster(roster):
    require(isinstance(roster, list) and len(roster) == 4, 'expected four roster entries')
    require({r['annotator_slot'] for r in roster} == set('ABCD'), 'roster slots differ')
    identities = [r['actual_identity'] for r in roster]
    require(all(isinstance(i, str) and i.strip() == i and bool(i) for i in identities)
            and len(set(identities)) == 4, 'actual identities must be distinct across slots')
    require(all(r['prior_cohort_exposure'] is False for r in roster), 'prior cohort exposure invalidates blinding')
    # Operator attestation only: names/aliases cannot establish real-world independence.


def producers():
    return dict(source_digests(), **{Path(__file__).name: transport.sha(Path(__file__).read_bytes())})


def freeze(preparation, output):
    plan = build_plan(preparation)
    output.mkdir(parents=False, exist_ok=False)
    raw = (encoded(plan) + '\n').encode()
    (output / 'plan.json').write_bytes(raw)
    (output / 'receipt.json').write_text(encoded(dict(contract=CONTRACT,
        status='complete_assignment_preparation_not_dispatched',
        file_sha256={'plan.json': transport.sha(raw)}, producer_sha256=producers(),
        hosted_requests=0, dispatch_authorized=False)) + '\n')
    return verify(preparation, output)


def verify(preparation, output):
    require({p.name for p in output.iterdir()} == {'plan.json', 'receipt.json'}, 'assignment file set differs')
    raw = (output / 'plan.json').read_bytes()
    receipt = transport.decode((output / 'receipt.json').read_bytes())
    expected = dict(contract=CONTRACT, status='complete_assignment_preparation_not_dispatched',
        file_sha256={'plan.json': transport.sha(raw)}, producer_sha256=producers(),
        hosted_requests=0, dispatch_authorized=False)
    require(receipt == expected and type(receipt['hosted_requests']) is int
            and receipt['dispatch_authorized'] is False, 'assignment receipt differs')
    plan = transport.decode(raw)
    require(plan == build_plan(preparation) and type(plan['hosted_requests']) is int
            and plan['dispatch_authorized'] is False, 'assignment plan differs')
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze', type=Path)
    mode.add_argument('--verify', type=Path)
    parser.add_argument('--roster', type=Path, help='optional private identity binding, never copied into frozen files')
    args = parser.parse_args()
    plan = freeze(args.preparation, args.freeze) if args.freeze else verify(args.preparation, args.verify)
    if args.roster:
        validate_roster(transport.decode(args.roster.read_bytes()))
    print(json.dumps(dict(status=plan['status'], verified=True, slots=len(plan['slots']),
                          roster_validated=bool(args.roster), dispatch_authorized=False)))


if __name__ == '__main__':
    main()
