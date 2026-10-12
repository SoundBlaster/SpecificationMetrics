from functools import partial
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from contrastive_decision_study import RUN as V1_RUN, validate as validate_v1
from contrastive_decision_study_v2 import OUTPUTS, POLICY, build, execute, inspect_results
from coreinfra_transport import post
from question_grouping import canonical, digest
from score_contrastive_decisions_v2 import score, summarize
from test_contrastive_decision_study import ANNOTATIONS, REFERENCE, mock_sender, response_for
from test_coreinfra_transport import FakeConnection


def make_run(path):
    run = Path(path)
    (run / 'manifest.json').write_bytes(canonical(build()))
    return run


def warned_sender(*, reject_first=False):
    rejected = False

    def sender(endpoint, wire, key, **kwargs):
        nonlocal rejected
        body = response_for(wire)
        if isinstance(body['answers'], dict):
            a = body['answers']['concern_kind']
            other = next(k for k in a['probabilities'] if k != a['choice'])
            a['probabilities'][a['choice']] = .90
            a['probabilities'][other] = .09
            if reject_first and not rejected:
                a['probabilities'][a['choice']] = .85  # 0.94: outside allowance.
                rejected = True
        return post(endpoint, wire, key, **kwargs,
                    connection_factory=lambda _: FakeConnection(body=canonical(body)), sleep=lambda _: None)
    return sender


class VersionedExecution(unittest.TestCase):
    def test_manifest_reuses_exact_v1_wires_but_binds_new_policy_and_implementations(self):
        v1, _, _ = validate_v1(V1_RUN)
        v2 = build()
        self.assertNotEqual(v1['study'], v2['study'])
        self.assertEqual(v1['requests'], v2['requests'])
        self.assertEqual(v1['input_sha256'], v2['input_sha256'])
        self.assertEqual(v2['acceptance_policy']['warning_absolute_allowance'], '0.01')
        self.assertEqual(v2['acceptance_policy']['probability_transform'], 'none')
        self.assertIn('score_contrastive_decisions_v2.py', v2['producer_digests'])

    def test_offline_modes_never_read_credentials_or_send_or_write_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            with patch('contrastive_decision_study_v2.os.environ') as env:
                env.get.side_effect = AssertionError('Offline must not read credentials')
                self.assertFalse(execute(run, sender=lambda *a, **k: self.fail('must not send'))['inference'])
            script = str(Path(__file__).with_name('contrastive_decision_study_v2.py'))
            result = json.loads(subprocess.check_output([sys.executable, script], timeout=30))
            self.assertFalse(result['inference'])
            self.assertFalse(result['manifest_frozen'])
            self.assertEqual(sorted(p.name for p in run.iterdir()), ['manifest.json'])

    def test_policy_and_producer_tampering_rejected_before_send(self):
        mutations = [lambda m: m['acceptance_policy'].update(warning_absolute_allowance='0.02'),
                     lambda m: m['producer_digests'].update({'decision_choice_contract_v2.py': 'stale'}),
                     lambda m: m.update(study='contrastive_mechanics_policy_native/v1')]
        for mutation in mutations:
            with tempfile.TemporaryDirectory() as tmp:
                run = make_run(tmp); manifest = build(); mutation(manifest)
                (run / 'manifest.json').write_bytes(canonical(manifest))
                with self.assertRaises(ValueError):
                    execute(run, live=True, sender=lambda *a, **k: self.fail('must not send'))
                self.assertFalse(any((run / name).exists() for name in OUTPUTS))

    def test_cli_preparation_is_exclusive_and_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / 'new-run'
            script = str(Path(__file__).with_name('contrastive_decision_study_v2.py'))
            result = json.loads(subprocess.check_output([sys.executable, script, '--prepare', '--run', str(run)], timeout=30))
            self.assertFalse(result['inference'])
            self.assertEqual(canonical(json.loads((run / 'manifest.json').read_text())), canonical(build()))
            self.assertEqual(sorted(p.name for p in run.iterdir()), ['manifest.json'])
            duplicate = subprocess.run([sys.executable, script, '--prepare', '--run', str(run)],
                                       capture_output=True, timeout=30)
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertEqual(sorted(p.name for p in run.iterdir()), ['manifest.json'])

    def test_warning_continues_to_48_without_retry_and_preserves_raw_confidence(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'COREINFRA_API_KEY': 'test-only-key'}):
            run = make_run(tmp)
            receipt = execute(run, live=True, sender=warned_sender())
            self.assertTrue(receipt['completed'])
            self.assertIsNone(receipt['stop_reason'])
            self.assertEqual((receipt['network_attempts'], receipt['potentially_billable_posts']), (48, 48))
            self.assertEqual((receipt['native_valid_responses'], receipt['native_invalid_responses'], receipt['warned_responses']),
                             (48, 0, 24))
            native = inspect_results(run)
            self.assertTrue(native['execution_complete'])
            self.assertTrue(native['operationally_complete'])
            self.assertEqual(native['warned_responses'], 24)
            for row in native['rows']:
                if row['provider'] == 'jev-coreinfra':
                    self.assertEqual(row['warnings'][0]['raw_total'], '0.99')
                    self.assertEqual(row['prediction']['answers']['concern_kind']['confidence'], .8)
                    self.assertEqual(max(row['prediction']['answers']['concern_kind']['probabilities'].values()), .9)
                else:
                    self.assertEqual(row['warnings'], [])
            report = score(run)
            self.assertEqual(report['warned_responses'], 24)
            self.assertTrue(report['operationally_complete'])
            for provider in report['providers']:
                for repeat in provider['repeats']:
                    self.assertTrue(repeat['H1']['supported'])
                    self.assertTrue(repeat['H2']['supported'])
                    self.assertTrue(repeat['H3_secondary']['supported'])
            self.assertNotIn('test-only-key', (run / 'responses.jsonl').read_text())
            before = {p.name: p.read_bytes() for p in run.iterdir()}
            with self.assertRaisesRegex(ValueError, 'Refusing to repeat'):
                execute(run, live=True, sender=lambda *a, **k: self.fail('must not send'))
            self.assertEqual(before, {p.name: p.read_bytes() for p in run.iterdir()})

    def test_rejected_answer_continues_but_completion_does_not_imply_usable_coverage(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'COREINFRA_API_KEY': 'test-only-key'}):
            run = make_run(tmp)
            receipt = execute(run, live=True, sender=warned_sender(reject_first=True))
            self.assertTrue(receipt['completed'])
            self.assertEqual((receipt['network_attempts'], receipt['native_invalid_responses']), (48, 1))
            native = inspect_results(run)
            self.assertTrue(native['execution_complete'])
            self.assertFalse(native['operationally_complete'])
            self.assertEqual(native['unattempted_request_ids'], [])
            bad = next(r for r in native['rows'] if r['native_status'] == 'invalid')
            self.assertIsNone(bad['prediction'])
            self.assertEqual(bad['rejection_code'], 'probability_mass_outside_allowance')
            report = score(run)
            jev = next(p for p in report['providers'] if p['provider'] == 'jev-coreinfra')
            self.assertFalse(jev['repeats'][bad['repeat'] - 1]['operationally_complete'])
            self.assertEqual(jev['repeats'][bad['repeat'] - 1]['H1']['planned'], 4)

    def test_identity_failure_and_transport_exhaustion_still_stop(self):
        transport = partial(post, connection_factory=lambda _: FakeConnection(fail_at='connect', error=ssl.SSLEOFError()),
                            sleep=lambda _: None)
        for sender, expected, attempts in ((mock_sender(invalid=True), 'native_identity_error', 1),
                                           (transport, 'transport_error', 3)):
            with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'COREINFRA_API_KEY': 'test-only-key'}):
                run = make_run(tmp)
                receipt = execute(run, live=True, sender=sender)
                self.assertFalse(receipt['completed'])
                self.assertEqual((receipt['stop_reason'], receipt['network_attempts']), (expected, attempts))
                native = inspect_results(run)
                self.assertFalse(native['execution_complete'])
                self.assertEqual(len(native['unattempted_request_ids']), 47)

    def test_all_144_reserved_attempts_supported_without_exceeding_cap(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'COREINFRA_API_KEY': 'test-only-key'}):
            run = make_run(tmp)
            receipt = execute(run, live=True, sender=mock_sender(connect_retries=True))
            self.assertEqual((receipt['network_attempts'], receipt['potentially_billable_posts']), (144, 48))
            self.assertTrue(inspect_results(run)['operationally_complete'])

    def test_ambiguous_success_never_becomes_usable_by_mass_warning(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'COREINFRA_API_KEY': 'test-only-key'}):
            run = make_run(tmp)
            receipt = execute(run, live=True, sender=mock_sender(fail_first_post=True))
            self.assertTrue(receipt['completed'])
            native = inspect_results(run)
            self.assertTrue(native['execution_complete'])
            self.assertFalse(native['operationally_complete'])
            self.assertEqual(native['rows'][0]['ambiguous_posts'], 1)
            report = score(run)
            affected = next(p for p in report['providers'] if p['provider'] == native['rows'][0]['provider'])
            self.assertFalse(affected['repeats'][0]['operationally_complete'])

    def test_interrupted_post_retains_unknown_status_and_blocks_reuse(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'COREINFRA_API_KEY': 'test-only-key'}):
            run = make_run(tmp)

            def interrupt(endpoint, wire, key, *, emit, **kwargs):
                identity = {'attempt': 1, 'wire_sha256': digest(wire), 'protocol': 'specmetrics.coreinfra-tls-retry/v1'}
                emit({**identity, 'event': 'attempt_started'})
                emit({**identity, 'event': 'post_may_start'})
                raise RuntimeError('never persist this error text')

            with self.assertRaises(RuntimeError):
                execute(run, live=True, sender=interrupt)
            native = inspect_results(run)
            self.assertFalse(native['execution_complete'])
            self.assertEqual(native['unattempted_request_ids'], [])
            self.assertEqual(len(native['attempt_status_unknown_request_ids']), 47)
            self.assertEqual(len(native['attempted_without_result_request_ids']), 1)
            self.assertNotIn('never persist this error text', (run / 'receipt.json').read_text())
            with self.assertRaisesRegex(ValueError, 'Refusing to repeat'):
                execute(run, live=True, sender=mock_sender())

    def test_saved_warnings_counters_and_lifecycle_cannot_override_raw_replay(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'COREINFRA_API_KEY': 'test-only-key'}):
            run = make_run(tmp)
            execute(run, live=True, sender=warned_sender())
            originals = {name: (run / name).read_bytes() for name in OUTPUTS}
            mutations = [('responses.jsonl', lambda r: r['validation'].update(warnings=[{'code': 'invented'}])),
                         ('responses.jsonl', lambda r: r['validation'].update(status='invalid')),
                         ('receipt.json', lambda r: r.update(warned_responses=0)),
                         ('receipt.json', lambda r: r.update(native_invalid_responses=1)),
                         ('receipt.json', lambda r: r.update(completed=False)),
                         ('receipt.json', lambda r: r.update(stop_reason='invented')),
                         ('receipt.json', lambda r: r.update(network_attempts=48.0))]
            for name, mutation in mutations:
                with self.subTest(name=name):
                    for output, raw in originals.items():
                        (run / output).write_bytes(raw)
                    if name.endswith('.jsonl'):
                        rows = [json.loads(line) for line in originals[name].splitlines()]
                        mutation(rows[0]); (run / name).write_bytes(b'\n'.join(canonical(r) for r in rows))
                    else:
                        receipt = json.loads(originals[name]); mutation(receipt)
                        (run / name).write_bytes(canonical(receipt))
                    with self.assertRaises(ValueError):
                        inspect_results(run)

    def test_raw_positive_H3_can_remain_unresolved_under_precision_assumption(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'COREINFRA_API_KEY': 'test-only-key'}):
            run = make_run(tmp)
            execute(run, live=True, sender=mock_sender())
            native = inspect_results(run)
            mapping = json.loads((REFERENCE / 'source-mapping.json').read_text())
            strata = {r['case_id']: r['stratum'] for r in mapping['cases']}
            for row in native['rows']:
                if row['provider'] != 'jev-coreinfra' or strata[row['case_id']] == 'withheld':
                    continue
                for axis, target in (('opportunity', 'eligible'), ('concern_kind', 'policy')):
                    answer = row['prediction']['answers'][axis]
                    value = .50 if strata[row['case_id']] == 'policy' else .49
                    other = 'excluded' if axis == 'opportunity' else 'mechanics'
                    answer['probabilities'] = {k: 0.0 for k in answer['probabilities']}
                    answer['probabilities'].update({target: value, other: 1 - value})
            result = summarize(native, ANNOTATIONS, mapping)
            jev = next(p for p in result['providers'] if p['provider'] == 'jev-coreinfra')
            for repeat in jev['repeats']:
                h3 = repeat['H3_secondary']
                self.assertEqual((h3['raw_directional_pairs'], h3['directional_pairs']), (4, 0))
                self.assertEqual(len(h3['unresolved_raw_positive_pair_ids']), 4)
                self.assertFalse(h3['supported'])


if __name__ == '__main__':
    unittest.main()
