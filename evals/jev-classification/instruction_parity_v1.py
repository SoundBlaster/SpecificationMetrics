"""Instruction-only Jev/Luna diagnostic reusing the unchanged 24-response Sol run."""
import argparse
import base64
import copy
import json
from pathlib import Path

from specification_core import TraceRecorder

import coreinfra_retry_run as transport
from coreinfra_transport import post
from decision_choice_contract_v2 import ChoiceContractError, ResponseIdentityError
from paired_blind_reference_v1 import AXES, require
from paired_retrieval_study_v1 import verify as verify_original
from prepare_retrieval_context_v1 import QUESTIONS
from retrieval_fact_adapter_v1 import RULES, producer_digests as adapter_inventory
from retrieval_fact_adapter_v1.context import NativeProposal
from retrieval_fact_adapter_v1.dependencies import local_closure
from retrieval_fact_adapter_v1.native import parse_response
from retrieval_index_v1.source import encoded
from sol_reference_repeatability_v1 import ANNOTATIONS, ROOT, RUN as SOL_RUN, verify as verify_sol
import sol_top_line_comparison_v1 as previous

STUDY = 'specmetrics.semantic-instruction-parity/v1'
ORIGINAL = previous.PREPARATION
PRIOR = ROOT / 'runs/2026-10-18-jev-luna-sol-comparison-v1'
PREPARATION = ROOT / 'runs/2026-10-18-semantic-instruction-parity-preparation-v1'
RUN = ROOT / 'runs/2026-10-18-semantic-instruction-parity-live-v1'


def source_digests():
    seeds = [Path(__file__).resolve(), ROOT / 'verify_instruction_parity_transport_v1.py']
    return {str(p.relative_to(ROOT)): transport.sha(p.read_bytes()) for p in local_closure(ROOT, seeds)}


def semantic_guidance():
    """Verbatim Sol guidance, plus the same category catalog in place of a file read."""
    config = transport.decode((SOL_RUN / 'configuration.json').read_bytes())
    brief = (ANNOTATIONS / 'annotation-brief.txt').read_bytes()
    rubric = (ANNOTATIONS / 'annotation-rubric.json').read_bytes()
    require(transport.sha(brief) == config['brief_sha256']
            and transport.sha(rubric) == config['rubric_sha256'], 'Sol instructions changed')
    paragraphs = brief.decode().strip().split('\n\n')
    require(len(paragraphs) == 3, 'unexpected Sol brief structure')
    require(transport.decode(rubric)['questions'] == QUESTIONS, 'original API/Sol rubric differs')
    catalog = {axis: question['criteria'] for axis, question in QUESTIONS.items()}
    return paragraphs[1], catalog


def aligned_instructions(original, guidance, catalog):
    return (original + '\n\n' + guidance + '\n\n'
            + 'annotation-rubric.json category definitions (embedded here; no file access required):\n'
            + encoded(catalog))


def portable_comparison(report):
    """Exclude only analysis-host diagnostics, never captured execution provenance."""
    result = copy.deepcopy(report)
    evidence = result['transport_evidence']
    evidence.pop('analysis_runtime_inventory', None)
    evidence.pop('analysis_runtime_matches_execution', None)
    for row in evidence.get('rows', []):
        row.pop('adapter_producer_sha256', None)
    return result


def expected():
    old_manifest = verify_original(ORIGINAL)
    verify_sol(SOL_RUN)
    prior_report = previous.score(PRIOR)
    require(portable_comparison(prior_report) == portable_comparison(transport.decode((PRIOR / 'comparison.json').read_bytes())),
            'previous comparison no longer reconstructs')
    prior_receipt = transport.decode((PRIOR / 'result-receipt.json').read_bytes())
    require(prior_receipt['producer_sha256'] == previous.producers()
            and prior_receipt['file_sha256'] == {
                str(p.relative_to(PRIOR)): transport.sha(p.read_bytes())
                for p in PRIOR.rglob('*') if p.is_file() and p.name != 'result-receipt.json'},
            'previous result receipt differs')
    guidance, catalog = semantic_guidance()
    manifest = copy.deepcopy(old_manifest)
    audits = []
    for request in manifest['requests']:
        before = transport.decode(request['wire_json'])
        after = copy.deepcopy(before)
        questions = (list(after['questions'].values()) if isinstance(after['questions'], dict)
                     else after['questions'])
        for question in questions:
            question['instructions'] = aligned_instructions(question['instructions'], guidance, catalog)
        # Everything outside question instructions stays byte/structurally identical.
        wire = encoded(after)
        audits.append(dict(request_id=request['request_id'], old_wire_sha256=request['wire_sha256'],
            new_wire_sha256=transport.sha(wire.encode()),
            unchanged_state_sha256=transport.sha(before.get('state', before.get('input')).encode()),
            changed_paths=['questions.*.instructions']))
        request.update(wire_json=wire, wire_sha256=transport.sha(wire.encode()))
    manifest.update(study=STUDY, study_source_digests=source_digests(),
        questions_sha256=transport.sha(encoded(dict(guidance=guidance, catalog=catalog, questions=QUESTIONS)).encode()),
        independent_reference_status='reuse_unchanged_sol61_medium_24_annotations_not_semantic_truth',
        live_authorization='User authorized instruction alignment and repeated Jev/Luna comparison; no new Sol calls.')
    audit = dict(study=STUDY, status='frozen_before_new_provider_observations',
        original_preparation_receipt_sha256=transport.sha((ORIGINAL / 'study-receipt.json').read_bytes()),
        prior_result_receipt_sha256=transport.sha((PRIOR / 'result-receipt.json').read_bytes()),
        sol_receipt_sha256=transport.sha((SOL_RUN / 'receipt.json').read_bytes()),
        sol_top_line_sha256=transport.sha((SOL_RUN / 'top-line.json').read_bytes()),
        sol_brief_sha256=transport.sha((ANNOTATIONS / 'annotation-brief.txt').read_bytes()),
        sol_rubric_sha256=transport.sha((ANNOTATIONS / 'annotation-rubric.json').read_bytes()),
        transferred_semantic_paragraph=guidance,
        transferred_semantic_paragraph_sha256=transport.sha(guidance.encode()),
        embedded_category_catalog=catalog, request_audits=audits,
        sol_reuse_reason='Same original state views, original four questions/categories and existing Sol semantic guidance; Sol inputs unchanged.',
        new_sol_calls=0, planned_requests=16, max_network_attempts=48,
        unchanged=['state including accepted_facts placeholders', 'retrieval hits and ranking',
                   'models/endpoints', 'request order', 'choice definitions', 'native validation and consistency rules',
                   'Sol annotations, prompt and rubric', 'agreement denominators'],
        remaining_differences=['Sol returns rationale/source quotes; native APIs return choice distributions.',
            'Sol has agent/file-read restrictions; native APIs receive embedded definitions.',
            'Provider backend revisions/decoding and internal question isolation are not attested.',
            'Sequential historical/current runs do not control stochastic or temporal drift.'],
        scoring=dict(reference_authority='agreement_with_Sol_not_semantic_accuracy',
            axes=list(AXES), primary_axes=list(previous.PRIMARY), planned_per_provider=8,
            all_axis_slots_per_provider=32, primary_axis_slots_per_provider=16,
            compare_prior='per-axis gains/losses and native conflicts; keep abstentions and missing coverage visible',
            incomplete='captured count only; no agreement until complete transport verification',
            semantic_accuracy=None, H1_H2_eligibility=False, automatic_fact_acceptance=False, metric_effect='none'))
    return manifest, audit


def freeze(output):
    manifest, audit = expected()
    output.mkdir(exist_ok=False)
    for name, value in [('manifest.json', manifest), ('instruction-audit.json', audit)]:
        (output / name).write_text(encoded(value) + '\n')
    (output / 'preparation-receipt.json').write_text(encoded(dict(study=STUDY,
        file_sha256={p.name: transport.sha(p.read_bytes()) for p in output.iterdir()},
        producer_sha256=source_digests(), hosted_requests=0)) + '\n')
    return verify(output)


def verify(preparation):
    manifest, audit = expected()
    require({p.name for p in preparation.iterdir()} ==
            {'manifest.json', 'instruction-audit.json', 'preparation-receipt.json'}, 'preparation inventory differs')
    for name, value in [('manifest.json', manifest), ('instruction-audit.json', audit)]:
        require((preparation / name).read_text() == encoded(value) + '\n', 'frozen instruction condition differs: ' + name)
    receipt = transport.decode((preparation / 'preparation-receipt.json').read_bytes())
    require(receipt == dict(study=STUDY, hosted_requests=0, producer_sha256=source_digests(),
        file_sha256={name: transport.sha((preparation / name).read_bytes())
                     for name in ('manifest.json', 'instruction-audit.json')}), 'preparation receipt differs')
    transport.load(preparation)
    return manifest


def stage(preparation, run):
    verify(preparation)
    run.mkdir(exist_ok=False)
    (run / 'manifest.json').write_bytes((preparation / 'manifest.json').read_bytes())
    (run / 'preparation-binding.json').write_text(encoded(dict(study=STUDY,
        preparation_receipt_sha256=transport.sha((preparation / 'preparation-receipt.json').read_bytes()),
        logical_request_limit=16, network_attempt_limit=48, semantic_retries_allowed=False, new_sol_calls=0)) + '\n')
    return transport.execute(run, live=False)


def check_run(preparation, run):
    manifest = verify(preparation)
    require((run / 'manifest.json').read_bytes() == (preparation / 'manifest.json').read_bytes(), 'execution manifest differs')
    require(transport.decode((run / 'preparation-binding.json').read_bytes()) == dict(study=STUDY,
        preparation_receipt_sha256=transport.sha((preparation / 'preparation-receipt.json').read_bytes()),
        logical_request_limit=16, network_attempt_limit=48, semantic_retries_allowed=False, new_sol_calls=0),
        'execution authorization/preparation differs')
    return manifest


def execute(preparation, run, *, live=False, sender=post):
    manifest = check_run(preparation, run)
    if not live:
        return transport.execute(run, live=False)
    require(not any((run / n).exists() for n in (*transport.OUTPUTS, 'execution-binding.json')), 'refuse to repeat a run')
    sources, runtime = source_digests(), adapter_inventory()
    pending = iter(manifest['requests'])

    def capture(endpoint, wire, key, **kwargs):
        request = next(pending)
        require(endpoint == request['endpoint'] and wire == request['wire_json'].encode(), 'sender schedule differs')
        require(source_digests() == sources, 'producer changed during execution')
        result = sender(endpoint, wire, key, **kwargs)
        raw = result.get('body')
        if result['status'] == 'http_response' and result['http_status'] == 200 and isinstance(raw, bytes):
            result['raw_body_sha256'] = transport.sha(raw)
            try:
                if isinstance(transport.decode(raw), dict):
                    result['raw_body_base64'] = base64.b64encode(raw).decode('ascii')
                    try:
                        parse_response(raw, provider=request['provider'], model=request['requested_model'])
                    except ResponseIdentityError as error:
                        result.update(status='native_identity_error', native_rejection_code=error.code)
                    except ChoiceContractError:
                        pass  # Native invalidity is evidence; never retry it for another answer.
            except (ValueError, UnicodeError):
                pass
        return result

    try:
        return transport.execute(run, live=True, sender=capture)
    finally:
        if (run / 'receipt.json').is_file():
            binding = dict(study=STUDY, status='local_execution_snapshot_not_remote_attestation',
                manifest_sha256=transport.sha((run / 'manifest.json').read_bytes()),
                file_sha256={n: transport.sha((run / n).read_bytes()) for n in transport.OUTPUTS if (run / n).is_file()},
                study_source_digests=sources, adapter_runtime_inventory=runtime,
                producers_unchanged=source_digests() == sources and adapter_inventory() == runtime)
            with (run / 'execution-binding.json').open('x') as stream:
                stream.write(encoded(binding) + '\n')


def adapt_request(request, raw):
    """Same native parser and Specification rules, metadata bound to the NEW wire."""
    report = dict(provider=request['provider'], requested_model=request['requested_model'],
        wire_sha256=request['wire_sha256'], response_sha256=transport.sha(raw),
        adapter_producer_sha256=adapter_inventory(), automatic_fact_acceptance=False, metric_effect='none')
    try:
        prediction = parse_response(raw, provider=request['provider'], model=request['requested_model'])
    except ChoiceContractError as error:
        return dict(report, native_status='invalid', status='rejected', prediction=None,
                    rejection_code=error.code, consistency_violations=[])
    labels = prediction['labels']
    candidate = NativeProposal(labels['concern_kind'], labels['evidence_confidence'],
                               labels['ownership'], labels['tool_responsibility'])
    recorder = TraceRecorder()
    violations = [code for spec, code in RULES if not spec.is_satisfied_by(candidate, recorder=recorder)]
    return dict(report, native_status='valid', status='needs_review' if violations else 'proposed_not_accepted',
        prediction=prediction, consistency_violations=violations,
        consistency_trace=[dict(name=e.name, outcome=e.outcome.value) for e in recorder.events])


def compare_prior(current, old):
    changes = {}
    for provider, report in current.items():
        before = old[provider]
        old_rows = {d['request_id']: d for d in before['details']}
        deltas = []
        for row in report['details']:
            prior = old_rows[row['request_id']]
            require(prior['sol_labels'] == row['sol_labels'], 'comparator changed between runs')
            deltas.append(dict(request_id=row['request_id'], case_id=row['case_id'], arm=row['arm'],
                before=prior['labels'], after=row['labels'], sol_labels=row['sol_labels'],
                changed_axes=[a for a in AXES if row['labels'][a] != prior['labels'][a]],
                gained_agreement=[a for a in AXES if a in prior['differing_axes'] and a not in row['differing_axes']],
                lost_agreement=[a for a in AXES if a not in prior['differing_axes'] and a in row['differing_axes']],
                before_conflicts=prior['consistency_violations'], after_conflicts=row['consistency_violations']))
        changes[provider] = dict(before_axis_matches=before['all_axis_matches'], after_axis_matches=report['all_axis_matches'],
            axis_match_delta=(report['all_axis_matches'] - before['all_axis_matches']
                             if report['agreement_status'] == 'complete_native_label_comparison' else None),
            before_primary_matches=before['primary_axis_matches'], after_primary_matches=report['primary_axis_matches'],
            before_coherent=before['coherent'], after_coherent=report['coherent'],
            before_native_valid=before['native_valid'], after_native_valid=report['native_valid'],
            gains=sum(len(d['gained_agreement']) for d in deltas), losses=sum(len(d['lost_agreement']) for d in deltas),
            details=deltas, evaluable=report['agreement_status'] == 'complete_native_label_comparison')
    return changes


def score(preparation, run):
    from verify_instruction_parity_transport_v1 import inspect
    manifest = check_run(preparation, run)
    evidence = inspect(preparation, run)
    references = {(v['case_id'], v['arm']): v['labels']
                  for v in transport.decode((SOL_RUN / 'top-line.json').read_bytes())['views']}
    current = previous.summarize(evidence.get('rows', []), manifest['requests'], references)
    old = previous.score(PRIOR)['providers']
    return dict(study=STUDY, preparation_receipt_sha256=transport.sha((preparation / 'preparation-receipt.json').read_bytes()),
        sol_top_line_sha256=transport.sha((SOL_RUN / 'top-line.json').read_bytes()),
        captured_response_rows=len((run / 'responses.jsonl').read_bytes().splitlines()) if (run / 'responses.jsonl').exists() else 0,
        transport_evidence=evidence, providers=current, comparison_to_prior=compare_prior(current, old),
        new_sol_calls=0, semantic_accuracy=None, H1_H2_eligibility=False,
        automatic_fact_acceptance=False, metric_effect='none')


def seal(preparation, run):
    result = score(preparation, run)
    require(portable_comparison(transport.decode((run / 'comparison.json').read_bytes())) == portable_comparison(result),
            'comparison does not reconstruct')
    receipt = dict(study=STUDY, status='complete' if result['transport_evidence']['transport_verified'] else 'incomplete',
        file_sha256={str(p.relative_to(run)): transport.sha(p.read_bytes()) for p in run.rglob('*')
                     if p.is_file() and p.name != 'result-receipt.json'}, producer_sha256=source_digests(),
        preparation_receipt_sha256=result['preparation_receipt_sha256'], new_sol_calls=0,
        semantic_accuracy=None, automatic_fact_acceptance=False)
    with (run / 'result-receipt.json').open('x') as stream:
        stream.write(encoded(receipt) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['freeze', 'verify', 'stage', 'execute', 'score', 'seal'])
    parser.add_argument('--preparation', type=Path, default=PREPARATION)
    parser.add_argument('--run', type=Path, default=RUN)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    if args.mode == 'freeze':
        result = freeze(args.preparation)
    elif args.mode == 'verify':
        result = verify(args.preparation)
    elif args.mode == 'stage':
        result = stage(args.preparation, args.run)
    elif args.mode == 'execute':
        result = execute(args.preparation, args.run, live=args.live)
    elif args.mode == 'seal':
        result = seal(args.preparation, args.run)
    else:
        result = score(args.preparation, args.run)
        with (args.run / 'comparison.json').open('x') as stream:
            stream.write(encoded(result) + '\n')
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ('requests', 'study_source_digests', 'transport_evidence', 'providers', 'comparison_to_prior', 'producer_sha256', 'file_sha256')}, indent=2))


if __name__ == '__main__':
    main()
