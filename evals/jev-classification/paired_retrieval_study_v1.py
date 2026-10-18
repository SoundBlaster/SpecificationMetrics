"""Freeze paired contexts and stage bounded transport runs; offline by default."""
import argparse
import copy
from dataclasses import asdict
import json
from pathlib import Path

import coreinfra_retry_run as transport
from coreinfra_transport import PROTOCOL, RetryPolicy
import prepare_retrieval_context_v1 as context
from retrieval_fact_adapter_v1.dependencies import local_closure
from retrieval_index_v1.local_model import LocalEncoder
from retrieval_index_v1.source import digest, encoded

ROOT = Path(__file__).resolve().parent
STUDY = 'specmetrics.paired-retrieval-facts/v1'
REVISION = '51c8d93cc385569864b3cd7f5040d4b3e0820a1b'
CASES = (
    ('R01', 'tools/subject_workspace_allocation_spec.py::WORKSPACE_ALLOCATION_SPEC',
     'Find the rule that binds workspace identity, source ref, expected commit, allocation authority and declaration digest.'),
    ('R02', 'tools/subject_source_write.py::_check_transition',
     'Find rules for appending one subject revision while preserving containment and disposition history.'),
    ('R03', 'tools/subject_source_write.py::parse_write_authorization',
     'Find how a subject write authorization is decoded into its typed representation.'),
    ('R04', 'tools/product_workspace_next_moves_support.py::safe_workspace_path',
     'Find the rule that rejects unsafe workspace paths, parent traversal and absolute paths.'),
)
INCLUDES = (
    'tools/subject_workspace_allocation_spec.py', 'tools/subject_source_write.py',
    'tools/product_workspace_next_moves_support.py', 'tools/subject_reviewed_record_spec.py',
    'tools/subject_transition_approval_spec.py',
)


def reference_view(case_id, arm, packet):
    view_id = 'view-' + digest(case_id + ':' + arm)[:16]
    return view_id, dict(state=packet['state']), dict(
        view_id=view_id, status='pending', annotator=None, evidence_confidence=None,
        concern_kind=None, ownership=None, tool_responsibility=None,
        rationale=None, source_locators=[], unresolved=[])


def source_digests():
    seeds = [ROOT / n for n in ('paired_retrieval_study_v1.py', 'paired_retrieval_execution_v1.py',
                               'verify_paired_retrieval_transport_v1.py', 'adapt_retrieval_facts_v1.py')]
    return {str(p.relative_to(ROOT)): digest(p.read_text()) for p in local_closure(ROOT, seeds)}


def manifest_from_cases(cases):
    requests = []
    if not 1 <= len(cases) <= 8 or len({c['case_id'] for c in cases}) != len(cases):
        raise ValueError('expected one to eight distinct cases')
    for index, case in enumerate(cases):
        arms = ('baseline', 'retrieval') if index % 2 == 0 else ('retrieval', 'baseline')
        providers = list(context.PROVIDERS)
        if index % 2:
            providers.reverse()
        for arm in arms:
            for provider in providers:
                request = next(r for r in case['packets'][arm]['requests'] if r['provider'] == provider)
                requests.append(dict(request, case_id=case['case_id'], arm=arm,
                                     request_id=case['case_id'] + '-' + arm + '-' + provider,
                                     preparation=case['case_id'] + '/' + arm))
    policy = RetryPolicy()
    return transport.decode(encoded(dict(protocol=PROTOCOL, study=STUDY, semantic_status='unscored',
                status='prepared_offline_not_live_authorized', requests=requests,
                retry_policy=asdict(policy), producer_digests=transport.producer_digests(),
                study_source_digests=source_digests(), planned_requests=len(requests),
                max_network_attempts=len(requests) * policy.max_attempts,
                questions_sha256=digest(encoded(context.QUESTIONS)),
                independent_reference_status='pending_blind_annotation_and_adjudication',
                live_authorization='Separate explicit authorization required for the frozen request/attempt budget.',
                metric_effect='none')))


def freeze(output, prepared_cases):
    """Only context changes between arms; identical fact plans and target data."""
    if len({p['state']['target']['id'] for _, p in prepared_cases}) != len(prepared_cases):
        raise ValueError('cohort targets must be distinct')
    cases = []
    for case_id, packet in prepared_cases:
        if not isinstance(case_id, str) or not case_id.isalnum():
            raise ValueError('invalid case locator')
        baseline = copy.deepcopy(packet)
        baseline['state']['retrieved_context'] = []
        baseline['state_sha256'] = digest(encoded(baseline['state']))
        baseline['requests'] = [context.wire(p, encoded(baseline['state'])) for p in context.PROVIDERS]
        baseline['retrieval'] = dict(baseline['retrieval'], returned=0, context_bytes=0, kind='context_withheld')
        cases.append(dict(case_id=case_id, packets=dict(baseline=baseline, retrieval=packet)))
    manifest = manifest_from_cases(cases)
    output.mkdir(parents=False, exist_ok=False)
    reference_index = []
    for case in cases:
        parent = output / case['case_id']
        parent.mkdir()
        for arm, packet in case['packets'].items():
            context.write_bundle(parent / arm, packet)
            blind_id, view, template = reference_view(case['case_id'], arm, packet)
            blind = output / 'blind' / blind_id
            blind.mkdir(parents=True)
            # One target/view per fresh annotation context. No arm name, model
            # output, author hypothesis or integrator labels in this packet.
            (blind / 'packet.json').write_text(encoded(view) + '\n')
            (blind / 'annotation-template.json').write_text(encoded(template) + '\n')
            reference_index.append(dict(case_id=case['case_id'], arm=arm, view_id=blind_id))
    (output / 'reference-index.json').write_text(encoded(dict(
        status='integrator_only_not_gold', views=reference_index)) + '\n')
    (output / 'manifest.json').write_text(encoded(manifest) + '\n')
    files = sorted(p for p in output.rglob('*') if p.is_file())
    (output / 'study-receipt.json').write_text(encoded(dict(study=STUDY,
        status='complete_preparation_not_live_authorized',
        file_sha256={str(p.relative_to(output)): transport.sha(p.read_bytes()) for p in files},
        hosted_requests=0, independent_reference_status=manifest['independent_reference_status'])) + '\n')
    verify(output)
    return manifest


def verify(preparation):
    receipt = transport.decode((preparation / 'study-receipt.json').read_bytes())
    actual = {str(p.relative_to(preparation)) for p in preparation.rglob('*') if p.is_file()}
    if (receipt['study'] != STUDY or receipt['status'] != 'complete_preparation_not_live_authorized'
            or type(receipt['hosted_requests']) is not int or receipt['hosted_requests'] != 0
            or receipt.get('independent_reference_status') != 'pending_blind_annotation_and_adjudication'
            or actual != set(receipt['file_sha256']) | {'study-receipt.json'}):
        raise ValueError('invalid study receipt')
    for name, sha in receipt['file_sha256'].items():
        if transport.sha((preparation / name).read_bytes()) != sha:
            raise ValueError('frozen study bytes differ: ' + name)
    manifest, _, _ = transport.load(preparation)
    if manifest['study'] != STUDY or manifest['study_source_digests'] != source_digests():
        raise ValueError('study producers differ')
    case_ids = list(dict.fromkeys(r['case_id'] for r in manifest['requests']))
    cases, reference_index = [], []
    for case_id in case_ids:
        if not case_id.isalnum():
            raise ValueError('invalid case locator')
        packets = {arm: context.verify_bundle(preparation / case_id / arm) for arm in ('baseline', 'retrieval')}
        left, right = (copy.deepcopy(packets[a]['state']) for a in ('baseline', 'retrieval'))
        if left.pop('retrieved_context') != []:
            raise ValueError('baseline leaked retrieval')
        right.pop('retrieved_context')
        if left != right or packets['baseline']['fact_plan'] != packets['retrieval']['fact_plan']:
            raise ValueError('pair changes more than retrieval context')
        for arm, packet in packets.items():
            view_id, view, template = reference_view(case_id, arm, packet)
            blind = preparation / 'blind' / view_id
            if ((blind / 'packet.json').read_text() != encoded(view) + '\n'
                    or (blind / 'annotation-template.json').read_text() != encoded(template) + '\n'):
                raise ValueError('blind reference input differs or contains annotations')
            reference_index.append(dict(case_id=case_id, arm=arm, view_id=view_id))
        cases.append(dict(case_id=case_id, packets=packets))
    if transport.decode((preparation / 'reference-index.json').read_bytes()) != dict(
            status='integrator_only_not_gold', views=reference_index):
        raise ValueError('reference mapping differs')
    if manifest != transport.decode(encoded(manifest_from_cases(cases))):
        raise ValueError('manifest differs from paired request reconstruction')
    return manifest


def stage(preparation, output):
    verify(preparation)
    output.mkdir(parents=False, exist_ok=False)
    (output / 'manifest.json').write_bytes((preparation / 'manifest.json').read_bytes())
    return transport.execute(output, live=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', type=Path, help='new frozen study directory')
    parser.add_argument('--repo', type=Path)
    parser.add_argument('--store', type=Path)
    parser.add_argument('--model-path', type=Path)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--stage', type=Path)
    args = parser.parse_args()
    if args.prepare:
        if not all((args.repo, args.store, args.model_path)) or args.verify or args.stage:
            parser.error('prepare requires repo/store/model-path and excludes other modes')
        encoder = LocalEncoder(args.model_path)
        packets = [(case, context.prepare(args.repo, '0al-spec/SpecGraph', REVISION, INCLUDES, (),
                    args.store, encoder, target, query)) for case, target, query in CASES]
        manifest = freeze(args.prepare, packets)
        print(json.dumps(dict(status=manifest['status'], requests=manifest['planned_requests'],
                              max_network_attempts=manifest['max_network_attempts'])))
    elif args.verify:
        result = stage(args.verify, args.stage) if args.stage else verify(args.verify)
        print(json.dumps(dict(validated=True, planned_requests=result['planned_requests'])))
    else:
        parser.error('select prepare or verify')


if __name__ == '__main__':
    main()
