import copy
from functools import partial
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from contrastive_decision_study import (INPUTS, OUTPUTS, PROTOCOL, REFERENCE, RUN,
                                       build, execute, inspect_results, validate)
from coreinfra_transport import post
from question_grouping import canonical, digest
from test_coreinfra_transport import FakeConnection

PACKET = json.loads((REFERENCE / 'case-packet.json').read_text())
ANNOTATIONS = json.loads((REFERENCE / 'independent-annotations.json').read_text())
QUESTIONS = PACKET['questions']
LABELS = {row['state_sha256']: row for row in ANNOTATIONS['annotations']}


def response_for(wire, *, invalid=False):
    body = json.loads(wire)
    labels = LABELS[digest(body.get('state', body.get('input')).encode('utf-8'))]
    answers = {}
    for axis, question in QUESTIONS.items():
        choice = labels[axis]
        answers[axis] = {'type': 'choice', 'choice': choice, 'confidence': 0.8,
                         'probabilities': {label: float(label == choice) for label in question['criteria']}}
    if 'input' in body:
        answers = [{**a, 'name': axis, 'probabilities': [{'value': label, 'probability': value}
                                                       for label, value in a['probabilities'].items()]}
                   for axis, a in answers.items()]
    return {'model': 'wrong-model' if invalid else body['model'], 'answers': answers,
            'usage': {'input_tokens': 10, 'output_tokens': 2}}


def mock_sender(*, invalid=False, fail_first_post=False, connect_retries=False):
    calls = [0]

    def sender(endpoint, wire, key, **kwargs):
        connections = [FakeConnection(body=canonical(response_for(wire, invalid=invalid)))]
        if connect_retries:
            connections[:0] = [FakeConnection(fail_at='connect', error=ssl.SSLEOFError()) for _ in range(2)]
        elif fail_first_post and calls[0] == 0:
            connections.insert(0, FakeConnection(fail_at='read', error=ssl.SSLEOFError()))
        calls[0] += 1
        iterator = iter(connections)
        return post(endpoint, wire, key, **kwargs, connection_factory=lambda _: next(iterator), sleep=lambda _: None)
    return sender


def make_run(path):
    run = Path(path)
    (run / 'manifest.json').write_bytes(canonical(build()))
    return run


class FrozenWires(unittest.TestCase):
    def test_identical_state_and_rubric_without_reference_leakage(self):
        manifest = build()
        self.assertEqual(len(manifest['requests']), 48)
        self.assertEqual(len({r['request_id'] for r in manifest['requests']}), 48)
        self.assertEqual(set(manifest['input_sha256']), set(INPUTS))
        by_repeat = {}
        for case in PACKET['cases']:
            rows = [r for r in manifest['requests'] if r['case_id'] == case['case_id']]
            self.assertEqual(len(rows), 4)
            states = []
            for row in rows:
                wire = row['wire_json'].encode('utf-8')
                self.assertEqual(digest(wire), row['wire_sha256'])
                body = json.loads(wire)
                state = body.get('state', body.get('input'))
                states.append(state)
                self.assertEqual(state.encode('utf-8'), canonical(case['state']))
                if row['provider'] == 'jev-coreinfra':
                    self.assertEqual(set(body), {'state', 'questions', 'model'})
                    self.assertEqual(body['questions'], QUESTIONS)
                else:
                    self.assertEqual(set(body), {'input', 'questions', 'model'})
                    reconstructed = {q['name']: {'type': q['type'], 'instructions': q['instructions'],
                                      'criteria': {v['value']: v['description'] for v in q['choices']}}
                                     for q in body['questions']}
                    self.assertEqual(reconstructed, QUESTIONS)
                by_repeat.setdefault((case['case_id'], row['repeat']), []).append(row['provider'])
            self.assertEqual(len(set(states)), 1)
            self.assertEqual(by_repeat[(case['case_id'], 1)], by_repeat[(case['case_id'], 2)][::-1])
        schedule = json.loads((REFERENCE / 'logical-schedule.json').read_text())['requests']
        self.assertEqual([r['request_id'] for r in manifest['requests']], [r['request_id'] for r in schedule])

    def test_saved_manifest_replays_and_all_criteria_are_frozen(self):
        manifest, _, _ = validate(RUN)
        plan = json.loads((REFERENCE / 'study-plan.json').read_text())
        self.assertEqual(manifest['criteria'], plan['criteria'])
        self.assertEqual(manifest['hypotheses'], plan['hypotheses'])
        self.assertIn('score_contrastive_decisions.py', manifest['producer_digests'])
        self.assertEqual(manifest['max_network_attempts'], 144)

    def test_manifest_tampering_fails_before_artifacts_or_network(self):
        mutations = [lambda m: m.update(max_network_attempts=145),
                     lambda m: m['requests'][0].update(wire_json='{}'),
                     lambda m: m['requests'][0].update(endpoint='https://evil.test'),
                     lambda m: m['requests'][0].update(provider='other'),
                     lambda m: m['producer_digests'].update({'score_contrastive_decisions.py': 'stale'}),
                     lambda m: m['input_sha256'].update({'independent-annotations.json': 'stale'}),
                     lambda m: m['criteria'].update(H1_pass='anything passes')]
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                run = make_run(tmp)
                manifest = build(); mutation(manifest)
                (run / 'manifest.json').write_bytes(canonical(manifest))
                with self.assertRaises(ValueError):
                    execute(run, live=True, sender=lambda *a, **k: self.fail('must not send'))
                self.assertFalse(any((run / name).exists() for name in OUTPUTS))

    def test_nonready_stale_or_inconsistent_review_rejected(self):
        for field, value in [('status', 'draft'), ('reference_sha256', 'stale'),
                             ('comparison', {}), ('label_overrides', ['override']), ('validator_sha256', 'stale')]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                reference = Path(tmp)
                for name in INPUTS:
                    shutil.copyfile(REFERENCE / name, reference / name)
                review = json.loads((reference / 'reference-review.json').read_text())
                review[field] = value
                (reference / 'reference-review.json').write_bytes(canonical(review))
                with self.assertRaises(ValueError):
                    build(reference)

    def test_default_cli_and_offline_executor_never_read_credentials_or_send(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            with patch('contrastive_decision_study.os.environ') as env:
                env.get.side_effect = AssertionError('must not read credentials')
                result = execute(run, sender=lambda *a, **k: self.fail('must not send'))
            self.assertFalse(result['inference'])
            output = subprocess.check_output([sys.executable, str(Path(__file__).with_name('contrastive_decision_study.py')),
                                              '--run', str(run)], timeout=30)
            self.assertFalse(json.loads(output)['inference'])
            self.assertEqual(sorted(p.name for p in run.iterdir()), ['manifest.json'])


class ExecutionEvidence(unittest.TestCase):
    def test_all_144_reserved_attempts_supported_and_run_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'COREINFRA_API_KEY': 'test-only-key'}):
            run = make_run(tmp)
            receipt = execute(run, live=True, sender=mock_sender(connect_retries=True))
            self.assertTrue(receipt['completed'])
            self.assertEqual((receipt['network_attempts'], receipt['potentially_billable_posts']), (144, 48))
            report = inspect_results(run)
            self.assertTrue(report['operationally_complete'])
            self.assertEqual(report['native_valid'], 48)
            before = {p.name: p.read_bytes() for p in run.iterdir()}
            with self.assertRaisesRegex(ValueError, 'Refusing to repeat'):
                execute(run, live=True, sender=lambda *a, **k: self.fail('must not send'))
            self.assertEqual(before, {p.name: p.read_bytes() for p in run.iterdir()})
            self.assertNotIn('test-only-key', (run / 'responses.jsonl').read_text())

    def test_ambiguous_success_is_visible_but_not_operationally_complete(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'COREINFRA_API_KEY': 'test-only-key'}):
            run = make_run(tmp)
            receipt = execute(run, live=True, sender=mock_sender(fail_first_post=True))
            self.assertEqual(receipt['ambiguous_posts'], 1)
            report = inspect_results(run)
            self.assertEqual(report['native_valid'], 48)
            self.assertFalse(report['operationally_complete'])
            self.assertTrue(report['rows'][0]['duplicate_execution_possible'])

    def test_native_invalid_stops_with_47_proven_unattempted_and_denominator_48(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'COREINFRA_API_KEY': 'test-only-key'}):
            run = make_run(tmp)
            receipt = execute(run, live=True, sender=mock_sender(invalid=True))
            self.assertEqual(receipt['stop_reason'], 'native_contract_invalid')
            self.assertEqual(receipt['network_attempts'], 1)
            report = inspect_results(run)
            self.assertEqual((report['planned_requests'], report['native_invalid']), (48, 1))
            self.assertEqual(len(report['unattempted_request_ids']), 47)
            self.assertEqual(report['attempt_status_unknown_request_ids'], [])

    def test_tls_exhaustion_stops_without_turning_error_into_abstention(self):
        sender = partial(post, connection_factory=lambda _: FakeConnection(fail_at='connect', error=ssl.SSLEOFError()),
                         sleep=lambda _: None)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'COREINFRA_API_KEY': 'test-only-key'}):
            run = make_run(tmp)
            receipt = execute(run, live=True, sender=sender)
            self.assertEqual((receipt['network_attempts'], receipt['potentially_billable_posts']), (3, 0))
            report = inspect_results(run)
            self.assertEqual(report['rows'][0]['native_status'], 'not_evaluated')
            self.assertIsNone(report['rows'][0]['prediction'])
            self.assertEqual(len(report['unattempted_request_ids']), 47)

    def test_interruption_preserves_unknown_post_status_and_blocks_reuse(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'COREINFRA_API_KEY': 'test-only-key'}):
            run = make_run(tmp)

            def interrupted(endpoint, wire, key, *, emit, **kwargs):
                identity = {'attempt': 1, 'wire_sha256': digest(wire), 'protocol': PROTOCOL}
                emit({**identity, 'event': 'attempt_started'})
                emit({**identity, 'event': 'post_may_start'})
                raise RuntimeError('test-only-sensitive-message')

            with self.assertRaises(RuntimeError):
                execute(run, live=True, sender=interrupted)
            report = inspect_results(run)
            self.assertEqual(len(report['attempted_without_result_request_ids']), 1)
            self.assertEqual(len(report['attempt_status_unknown_request_ids']), 47)
            self.assertEqual(report['unattempted_request_ids'], [])
            self.assertIsNone(report['receipt']['ambiguous_posts'])
            self.assertNotIn('test-only-sensitive-message', (run / 'receipt.json').read_text())

    def test_evidence_tampering_and_dropped_results_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'COREINFRA_API_KEY': 'test-only-key'}):
            run = make_run(tmp)
            execute(run, live=True, sender=mock_sender(invalid=True))
            originals = {name: (run / name).read_bytes() for name in OUTPUTS}
            mutations = [('responses.jsonl', lambda r: r.update(wire_sha256='stale')),
                         ('responses.jsonl', lambda r: r.update(ambiguous_posts=99)),
                         ('responses.jsonl', lambda r: r.update(ambiguous_posts=False)),
                         ('responses.jsonl', lambda r: r.update(status='invented')),
                         ('attempts.jsonl', lambda r: r.update(attempt=2)),
                         ('receipt.json', lambda r: r.update(manifest_sha256='stale')),
                         ('receipt.json', lambda r: r.update(native_valid_responses=1))]
            for name, mutation in mutations:
                with self.subTest(name=name):
                    for output, raw in originals.items():
                        (run / output).write_bytes(raw)
                    lines = originals[name].splitlines() if name.endswith('.jsonl') else [originals[name]]
                    first = json.loads(lines[0]); mutation(first); lines[0] = canonical(first)
                    (run / name).write_bytes(b'\n'.join(lines))
                    with self.assertRaises(ValueError):
                        inspect_results(run)
            for output, raw in originals.items():
                (run / output).write_bytes(raw)
            (run / 'responses.jsonl').write_bytes(b'')
            with self.assertRaises(ValueError):
                inspect_results(run)


if __name__ == '__main__':
    unittest.main()
