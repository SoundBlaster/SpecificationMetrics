import ssl
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import coreinfra_retry_run as transport
from coreinfra_transport import post
from paired_retrieval_execution_v1 import execute
from paired_retrieval_study_v1 import freeze, stage, verify
from prepare_retrieval_context_v1 import prepare
from retrieval_index_v1.source import encoded
from test_coreinfra_transport import FakeConnection
from test_retrieval_context_v1 import Encoder
from test_retrieval_fact_adapter_v1 import response
from test_retrieval_index_v1 import CODE
from verify_paired_retrieval_transport_v1 import inspect


class PairedStudyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        def git(*args):
            subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True)
        git('init', '-q')
        git('config', 'user.name', 'Paired fixture')
        git('config', 'user.email', 'paired@example.invalid')
        for name in ('a', 'b', 'c', 'd'):
            (self.repo / (name + '.py')).write_text(CODE)
        git('add', '-A')
        git('commit', '-qm', 'fixture')
        self.packets = [(name.upper(), prepare(self.repo, 'fixture', 'HEAD', ('*.py',), (),
                        self.root / 'index.sqlite', Encoder(), name + '.py::allowed', 'Find positive value rules'))
                        for name in ('a', 'b', 'c', 'd')]
        self.preparation = self.root / 'preparation'
        freeze(self.preparation, self.packets[:1])
        self.run = self.root / 'run'
        stage(self.preparation, self.run)

    def sender(self, *, failure=None, mutate=None):
        calls = []
        def send(endpoint, wire, key, **kwargs):
            calls.append((endpoint, wire))
            provider = 'jev-coreinfra' if endpoint.endswith('/systemone') else 'luna-decision-coreinfra'
            body = response(provider)
            if mutate:
                mutate(body)
            connections = [FakeConnection(body=encoded(body).encode())]
            if failure and len(calls) == 1:
                connections.insert(0, FakeConnection(fail_at=failure, error=ssl.SSLEOFError()))
            connections = iter(connections)
            return post(endpoint, wire, key, **kwargs, connection_factory=lambda _: next(connections),
                        sleep=lambda _: None)
        return send, calls

    def run_fake(self, **kwargs):
        sender, calls = self.sender(**kwargs)
        with patch.dict('os.environ', COREINFRA_API_KEY='unit-test-not-a-real-key'):
            receipt = execute(self.preparation, self.run, live=True, sender=sender)
        return receipt, calls

    def rebind(self):
        path = self.run / 'execution-binding.json'
        binding = transport.decode(path.read_bytes())
        binding['file_sha256'] = {n: transport.sha((self.run / n).read_bytes()) for n in transport.OUTPUTS}
        path.write_text(encoded(binding))

    def test_balanced_four_case_plan_changes_only_retrieved_context(self):
        output = self.root / 'four'
        manifest = freeze(output, self.packets)
        self.assertEqual(verify(output), manifest)
        self.assertEqual((manifest['planned_requests'], manifest['max_network_attempts']), (16, 48))
        self.assertEqual([manifest['requests'][i]['arm'] for i in (0, 4, 8, 12)],
                         ['baseline', 'retrieval', 'baseline', 'retrieval'])
        for case, _ in self.packets:
            states = [transport.decode((output / case / arm / 'packet.json').read_bytes())['state']
                      for arm in ('baseline', 'retrieval')]
            self.assertEqual(states[0].pop('retrieved_context'), [])
            self.assertTrue(states[1].pop('retrieved_context'))
            self.assertEqual(*states)
        templates = list((output / 'blind').glob('*/annotation-template.json'))
        self.assertEqual(len(templates), 8)
        for path in templates:
            template = transport.decode(path.read_bytes())
            self.assertEqual(template['status'], 'pending')
            self.assertIsNone(template['concern_kind'])
            self.assertNotIn('arm', template)
            self.assertNotIn('provider', template)

    def test_offline_stage_never_reads_key_or_sends(self):
        with patch('coreinfra_retry_run.os.environ.get', side_effect=AssertionError('no key access')):
            result = execute(self.preparation, self.run, sender=lambda *a, **kw: self.fail('no network'))
        self.assertFalse(result['inference'])
        self.assertFalse((self.run / 'receipt.json').exists())
        self.assertEqual(inspect(self.preparation, self.run)['status'], 'incomplete_transport_evidence')

    def test_complete_native_run_is_bound_to_all_four_exact_wires_and_bodies(self):
        receipt, calls = self.run_fake(failure='connect')
        report = inspect(self.preparation, self.run)
        self.assertEqual((receipt['network_attempts'], receipt['potentially_billable_posts']), (5, 4))
        self.assertEqual(len(calls), 4)
        self.assertTrue(report['transport_verified'])
        self.assertTrue(report['operationally_complete'])
        self.assertTrue(report['native_contract_valid'])
        self.assertEqual(len(report['pairs']), 2)
        self.assertTrue(all(p['changed_labels'] is False for p in report['pairs']))
        self.assertTrue(all(r['semantic_correctness_verified'] is False for r in report['rows']))
        self.assertEqual(report['metric_effect'], 'none')
        with self.assertRaisesRegex(ValueError, 'repeat or overwrite'):
            execute(self.preparation, self.run, live=True)

    def test_after_post_retry_retains_ambiguity_without_claiming_clean_operational_pair(self):
        receipt, _ = self.run_fake(failure='read')
        report = inspect(self.preparation, self.run)
        self.assertEqual(receipt['ambiguous_posts'], 1)
        self.assertTrue(receipt['duplicate_execution_possible'])
        self.assertTrue(report['transport_verified'])
        self.assertFalse(report['operationally_complete'])

    def test_identity_mismatch_stops_run_and_never_attributes_a_pair(self):
        receipt, calls = self.run_fake(mutate=lambda b: b.update(model='wrong-model'))
        self.assertEqual(len(calls), 1)
        self.assertFalse(receipt['completed'])
        self.assertEqual(receipt['stop_reason'], 'native_identity_error')
        row = transport.decode((self.run / 'responses.jsonl').read_bytes())
        self.assertIn('raw_body_base64', row)
        report = inspect(self.preparation, self.run)
        self.assertFalse(report['transport_verified'])
        self.assertEqual(report['pairs'], [])

    def test_native_invalidity_is_not_transport_failure_or_semantic_success(self):
        def mutate(body):
            if isinstance(body['answers'], dict):
                body['answers']['tool_responsibility']['confidence'] = 2
            else:
                body['answers'][0]['confidence'] = 2
        self.run_fake(mutate=mutate)
        report = inspect(self.preparation, self.run)
        self.assertTrue(report['transport_verified'])
        self.assertFalse(report['native_contract_valid'])
        self.assertTrue(all(p['changed_labels'] is None for p in report['pairs']))

    def test_receipt_ledger_and_response_mismatches_fail_even_if_checksums_are_rebound(self):
        self.run_fake()
        originals = {n: (self.run / n).read_bytes() for n in (*transport.OUTPUTS, 'execution-binding.json')}
        for mutation in ('counter', 'row_identity', 'event_identity', 'raw_body', 'extra_event', 'runtime'):
            with self.subTest(mutation=mutation):
                for n, raw in originals.items():
                    (self.run / n).write_bytes(raw)
                if mutation == 'counter':
                    path = self.run / 'receipt.json'
                    value = transport.decode(path.read_bytes())
                    value['network_attempts'] += 1
                    path.write_text(encoded(value))
                elif mutation in ('row_identity', 'raw_body'):
                    path = self.run / 'responses.jsonl'
                    rows = [transport.decode(line) for line in path.read_bytes().splitlines()]
                    rows[0]['request_id' if mutation == 'row_identity' else 'raw_body_base64'] = 'wrong'
                    path.write_text(''.join(encoded(r) + '\n' for r in rows))
                elif mutation in ('event_identity', 'extra_event'):
                    path = self.run / 'attempts.jsonl'
                    events = [transport.decode(line) for line in path.read_bytes().splitlines()]
                    if mutation == 'event_identity':
                        events[0]['wire_sha256'] = '0' * 64
                    else:
                        events.append(events[0])
                    path.write_text(''.join(encoded(e) + '\n' for e in events))
                else:
                    path = self.run / 'execution-binding.json'
                    value = transport.decode(path.read_bytes())
                    value['adapter_runtime_inventory'] = {'@runtime/python': '0' * 64}
                    path.write_text(encoded(value))
                self.rebind()
                with self.assertRaises(ValueError):
                    inspect(self.preparation, self.run)

    def test_corrupt_preparation_metadata_and_prelabeled_blind_view_fail_closed(self):
        receipt_path = self.preparation / 'study-receipt.json'
        original = receipt_path.read_bytes()
        receipt = transport.decode(original)
        receipt['hosted_requests'] = False
        receipt_path.write_text(encoded(receipt))
        with self.assertRaises(ValueError):
            verify(self.preparation)
        receipt_path.write_bytes(original)
        template = next((self.preparation / 'blind').glob('*/annotation-template.json'))
        value = transport.decode(template.read_bytes())
        value['concern_kind'] = 'policy'
        template.write_text(encoded(value))
        receipt = transport.decode(original)
        receipt['file_sha256'][str(template.relative_to(self.preparation))] = transport.sha(template.read_bytes())
        receipt_path.write_text(encoded(receipt))
        with self.assertRaisesRegex(ValueError, 'contains annotations'):
            verify(self.preparation)

    def test_interruption_preserves_partial_receipt_and_does_not_assume_no_post(self):
        def interrupt(endpoint, wire, key, **kwargs):
            from coreinfra_transport import PROTOCOL
            identity = dict(protocol=PROTOCOL, wire_sha256=transport.sha(wire), attempt=1)
            kwargs['emit'](dict(identity, event='attempt_started'))
            kwargs['emit'](dict(identity, event='post_may_start'))
            raise KeyboardInterrupt()
        with patch.dict('os.environ', COREINFRA_API_KEY='unit-test-not-a-real-key'):
            with self.assertRaises(KeyboardInterrupt):
                execute(self.preparation, self.run, live=True, sender=interrupt)
        receipt = transport.decode((self.run / 'receipt.json').read_bytes())
        self.assertIsNone(receipt['ambiguous_posts'])
        self.assertEqual(receipt['potentially_billable_posts'], 1)
        self.assertFalse(inspect(self.preparation, self.run)['transport_verified'])


if __name__ == '__main__':
    unittest.main()
