"""Read-only routing replay of pinned native observations; no model invocation."""
import base64
import hashlib
import json
from pathlib import Path

from retrieval_fact_adapter_v1.dependencies import local_closure
from retrieval_fact_adapter_v1.native import parse_response
from semantic_review_routing_v1 import POLICY, evaluate
from semantic_review_routing_v1.context import CapturedAssessment, DecisionBinding, Labels, RoutingContext

ROOT = Path(__file__).resolve().parent
RUN = ROOT / 'runs/2026-10-18-semantic-instruction-parity-live-v1'
RECEIPT_SHA256 = '8c7dd390fae7dd90a3480d7db795d0505f6f98ad9ab180b6692457c496c37155'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def state_text(wire, provider):
    field = {'jev-coreinfra': 'state', 'luna-decision-coreinfra': 'input'}[provider]
    check(isinstance(wire.get(field), str), 'provider state field is missing or invalid')
    return wire[field]


def read_pinned_run(run=RUN):
    run = Path(run)
    raw = (run / 'result-receipt.json').read_bytes()
    check(sha(raw) == RECEIPT_SHA256, 'native receipt differs from pinned observation')
    receipt = json.loads(raw)
    files = {str(p.relative_to(run)): sha(p.read_bytes()) for p in run.rglob('*')
             if p.is_file() and p.name != 'result-receipt.json'}
    check(files == receipt['file_sha256'], 'native run inventory differs')
    for name, expected in receipt['producer_sha256'].items():
        path = (ROOT / name).resolve()
        check(path.is_relative_to(ROOT), 'producer path escapes evaluation root')
        check(sha(path.read_bytes()) == expected, 'frozen native producer differs: ' + name)
    manifest = json.loads((run / 'manifest.json').read_text())
    responses = [json.loads(line) for line in (run / 'responses.jsonl').read_text().splitlines()]
    requests = {r['request_id']: r for r in manifest['requests']}
    check(len(requests) == len(manifest['requests']) == len(responses) == 16, 'native cohort is incomplete')
    check(len({r['request_id'] for r in responses}) == 16, 'duplicate native response')
    check(set(requests) == {r['request_id'] for r in responses}, 'response/request identities differ')
    return requests, responses


def replay(run=RUN):
    requests, responses = read_pinned_run(run)
    cases = []
    for response in responses:
        request = requests[response['request_id']]
        wire = json.loads(request['wire_json'])
        check(sha(request['wire_json'].encode()) == request['wire_sha256'] == response['wire_sha256'],
              'response is not bound to the captured request')
        raw = base64.b64decode(response['raw_body_base64'], validate=True)
        check(sha(raw) == response['raw_body_sha256'], 'native response digest differs')
        check(response['status'] == 'json_received' and response['http_status'] == 200,
              'native response did not complete')
        labels = parse_response(raw, provider=request['provider'], model=request['requested_model'])['labels']
        raw_state = state_text(wire, request['provider'])
        state = json.loads(raw_state)
        source = state['target']['source']
        check(sha(source['code'].encode()) == source['excerpt_sha256'].removeprefix('sha256:'),
              'target source excerpt digest differs')
        binding = DecisionBinding(repository=state['evaluation_scope']['repository'], revision=source['revision'],
            path=source['path'], start_line=source['start_line'], end_line=source['end_line'],
            decision_id=state['target']['id'], evidence_sha256=sha(raw_state.encode()),
            rubric_version='semantic-instruction-parity-v1', category_version='four-axis-choice-v1',
            prompt_config_sha256=sha(json.dumps(wire['questions'], sort_keys=True).encode()))
        captured = CapturedAssessment(status='valid', provider=request['provider'],
            requested_model=request['requested_model'], returned_model=json.loads(raw)['model'],
            response_sha256=sha(raw), binding=binding, labels=Labels(**labels))
        result = evaluate(RoutingContext(expected=binding, expected_provider=request['provider'],
                                         expected_model=request['requested_model'],
                                         assessment=captured))
        cases.append(dict(request_id=request['request_id'], case_id=request['case_id'], arm=request['arm'],
                          provider=request['provider'], route=result))
    summaries = {p: {route: sum(c['provider'] == p and c['route']['route'] == route for c in cases)
                    for route in ('retain_proposal', 'ordinary_review', 'stop_incomplete')}
                 for p in sorted({c['provider'] for c in cases})}
    producers = {str(p.relative_to(ROOT)): sha(p.read_bytes())
                 for p in local_closure(ROOT, [Path(__file__).resolve()])}
    return dict(policy=POLICY, observation_receipt_sha256=RECEIPT_SHA256, producer_sha256=producers,
                scope='retrospective_first_stage_routing_only_no_review_resolution',
                summaries=summaries, cases=cases, hosted_requests=0, new_sol_calls=0,
                automatic_fact_acceptance=False, metric_effect='none', write_authority=False,
                semantic_accuracy=None, calibrated_uncertainty_enabled=False)


if __name__ == '__main__':
    result = replay()
    print(json.dumps({k: result[k] for k in ('policy', 'scope', 'summaries', 'hosted_requests')}, indent=2))
