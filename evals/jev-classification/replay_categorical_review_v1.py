"""Replay the captured Jev cohort through SDK categorical results and review preparation."""
import base64
import argparse
import json

from categorical_review_bridge_v1 import bind, replay_jev_capture
from replay_semantic_review_routing_v1 import read_pinned_run, sha
from semantic_review_routing_v1.context import CapturedAssessment, DecisionBinding, RoutingContext
from structured_semantic_review_v1.preparation import encoded, request_sha256


def case_input(item):
    wire = json.loads(item['wire_json'])
    state = json.loads(wire['state'])
    source = state['target']['source']
    binding = DecisionBinding(repository=state['evaluation_scope']['repository'], revision=source['revision'],
        path=source['path'], start_line=source['start_line'], end_line=source['end_line'],
        decision_id=state['target']['id'], evidence_sha256=sha(wire['state'].encode()),
        rubric_version='semantic-instruction-parity-v1', category_version='four-axis-choice-v1',
        prompt_config_sha256=sha(json.dumps(wire['questions'], sort_keys=True).encode()))
    context = RoutingContext(expected=binding, expected_provider=item['provider'],
        expected_model=item['requested_model'], assessment=CapturedAssessment(status='not_run',
            provider=item['provider'], requested_model=item['requested_model']))
    return bind(context, state_json=wire['state'], questions_json=encoded(wire['questions']))


def saved_review(plan):
    """Reuse exactly the pinned historical review after full offline verification."""
    import rich_review_pilot_v1 as pilot
    receipt = (pilot.RUN / 'result-receipt.json').read_bytes()
    if sha(receipt) != '25bc5df1412d62b8daf1ee2d129bc9e3e39161c4816d486e5dea36f905eedcbd':
        raise ValueError('saved review receipt differs')
    pilot.verify_result(pilot.PREPARATION, pilot.RUN)
    manifest = json.loads((pilot.RUN / 'manifest.json').read_bytes())
    if plan.review is None or request_sha256(plan.review) != manifest['request_sha256']:
        raise ValueError('saved review belongs to a different task')
    row = json.loads((pilot.RUN / 'response.json').read_bytes())
    return plan.inspect_review(base64.b64decode(row['raw_body_base64'], validate=True),
        captured_request_sha256=row['request_sha256'], execution_status='completed')


def replay(*, reuse_saved_review=False):
    requests, responses = read_pinned_run()
    cases, plans = [], {}
    for row in responses:
        item = requests[row['request_id']]
        if item['provider'] != 'jev-coreinfra':
            continue
        raw = base64.b64decode(row['raw_body_base64'], validate=True)
        if (sha(raw) != row['raw_body_sha256'] or sha(item['wire_json'].encode()) != item['wire_sha256']
                or item['wire_sha256'] != row['wire_sha256'] or row['status'] != 'json_received'):
            raise ValueError('native capture identity differs')
        plan = replay_jev_capture(case_input(item), raw, http_status=row['http_status'])
        plans[item['request_id']] = plan
        report = plan.report()
        if reuse_saved_review and plan.review is not None:
            report['review_inspection'] = saved_review(plan)
            report['review_status'] = report['review_inspection']['review_status']
        cases.append(dict(request_id=item['request_id'], case_id=item['case_id'], arm=item['arm'], report=report))
    counts = {route: sum(c['report']['original_route']['route'] == route for c in cases)
              for route in ('retain_proposal', 'ordinary_review', 'stop_incomplete')}
    return dict(hosted_requests=0, comparison_scope='SDK_replay_not_new_model_quality',
                reused_reviews=sum('review_inspection' in c['report'] for c in cases),
                automatic_fact_acceptance=False, metric_effect='none', counts=counts, cases=cases), plans


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reuse-saved-review', action='store_true',
                        help='Reuse the pinned historical Luna receipt only if the complete task matches.')
    print(json.dumps(replay(reuse_saved_review=parser.parse_args().reuse_saved_review)[0],
                     ensure_ascii=False, indent=2))
