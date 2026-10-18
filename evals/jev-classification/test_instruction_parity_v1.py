import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import instruction_parity_v1 as parity
from coreinfra_retry_run import decode, sha
from coreinfra_transport import post
from retrieval_index_v1.source import encoded
from test_coreinfra_transport import FakeConnection
from test_retrieval_fact_adapter_v1 import response
from test_sol_top_line_comparison_v1 import fixture
from verify_instruction_parity_transport_v1 import inspect


class InstructionParityTests(unittest.TestCase):
    def test_frozen_live_run_reconstructs_offline_and_keeps_sol_receipt(self):
        result = parity.score(parity.PREPARATION, parity.RUN)
        recorded = decode((parity.RUN / 'comparison.json').read_bytes())
        self.assertEqual(parity.portable_comparison(result), parity.portable_comparison(recorded))
        self.assertTrue(result['transport_evidence']['operationally_complete'])
        self.assertTrue(result['transport_evidence']['native_contract_valid'])
        self.assertEqual(result['new_sol_calls'], 0)
        jev, luna = (result['providers'][p] for p in ('jev-coreinfra', 'luna-decision-coreinfra'))
        self.assertEqual((jev['all_axis_matches'], jev['primary_axis_matches'], jev['consistency_review']), (31, 16, 1))
        self.assertEqual((luna['all_axis_matches'], luna['primary_axis_matches'], luna['consistency_review']), (18, 9, 2))
        receipt = decode((parity.RUN / 'result-receipt.json').read_bytes())
        self.assertEqual(receipt['producer_sha256'], parity.source_digests())
        self.assertEqual(receipt['file_sha256'], {str(p.relative_to(parity.RUN)): sha(p.read_bytes())
            for p in parity.RUN.rglob('*') if p.is_file() and p.name != 'result-receipt.json'})
        self.assertEqual(receipt['preparation_receipt_sha256'], result['preparation_receipt_sha256'])
        self.assertEqual(receipt['new_sol_calls'], 0)
        self.assertFalse(receipt['automatic_fact_acceptance'])
        self.assertIsNone(receipt['semantic_accuracy'])

    def test_cross_host_replay_changes_only_analysis_diagnostics(self):
        frozen = decode((parity.PRIOR / 'comparison.json').read_bytes())
        other_host = copy.deepcopy(frozen)
        evidence = other_host['transport_evidence']
        evidence['analysis_runtime_inventory'] = {'@runtime/python': 'different'}
        evidence['analysis_runtime_matches_execution'] = False
        for row in evidence['rows']:
            row['adapter_producer_sha256'] = {'@runtime/python': 'different'}
        self.assertEqual(parity.portable_comparison(frozen), parity.portable_comparison(other_host))
        # Captured execution provenance, labels and raw body identity remain strict.
        for field in ('recorded_execution_runtime_inventory', 'raw_file_sha256'):
            mutated = copy.deepcopy(other_host)
            mutated['transport_evidence'][field] = {}
            self.assertNotEqual(parity.portable_comparison(frozen), parity.portable_comparison(mutated))
        other_host['providers']['jev-coreinfra']['all_axis_matches'] -= 1
        self.assertNotEqual(parity.portable_comparison(frozen), parity.portable_comparison(other_host))

    def test_only_question_instructions_change_and_sol_inputs_are_reused(self):
        manifest, audit = parity.expected()
        original = parity.verify_original(parity.ORIGINAL)
        guidance, catalog = parity.semantic_guidance()
        self.assertEqual(audit['new_sol_calls'], 0)
        self.assertEqual((manifest['planned_requests'], manifest['max_network_attempts']), (16, 48))
        self.assertEqual(audit['sol_top_line_sha256'], sha((parity.SOL_RUN / 'top-line.json').read_bytes()))
        for old, new in zip(original['requests'], manifest['requests']):
            left, right = decode(old['wire_json']), decode(new['wire_json'])
            old_questions = list(left['questions'].values()) if isinstance(left['questions'], dict) else left['questions']
            new_questions = list(right['questions'].values()) if isinstance(right['questions'], dict) else right['questions']
            for before, after in zip(old_questions, new_questions):
                self.assertEqual(after['instructions'], parity.aligned_instructions(before['instructions'], guidance, catalog))
                after['instructions'] = before['instructions']
            self.assertEqual(left, right)
            self.assertEqual({k: v for k, v in old.items() if k not in ('wire_json', 'wire_sha256')},
                             {k: v for k, v in new.items() if k not in ('wire_json', 'wire_sha256')})
        self.assertEqual(guidance, (parity.ANNOTATIONS / 'annotation-brief.txt').read_text().strip().split('\n\n')[1])
        self.assertEqual(catalog, {a: q['criteria'] for a, q in parity.QUESTIONS.items()})

    def test_rebound_checksum_cannot_change_states_instructions_or_attempt_budget(self):
        for field in ('state', 'instructions', 'budget'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                preparation = Path(directory) / 'preparation'
                parity.freeze(preparation)
                path = preparation / 'manifest.json'
                manifest = decode(path.read_bytes())
                if field == 'budget':
                    manifest['max_network_attempts'] = 49
                else:
                    request = manifest['requests'][0]
                    wire = decode(request['wire_json'])
                    if field == 'state':
                        wire['state'] += ' extra evidence'
                    else:
                        next(iter(wire['questions'].values()))['instructions'] += ' Select policy.'
                    request['wire_json'] = encoded(wire)
                    request['wire_sha256'] = sha(request['wire_json'].encode())
                path.write_text(encoded(manifest) + '\n')
                receipt_path = preparation / 'preparation-receipt.json'
                receipt = decode(receipt_path.read_bytes())
                receipt['file_sha256']['manifest.json'] = sha(path.read_bytes())
                receipt_path.write_text(encoded(receipt))
                with self.assertRaises(ValueError):
                    parity.verify(preparation)

    def test_synthetic_transport_capture_replay_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            preparation, run = (Path(directory) / n for n in ('preparation', 'run'))
            parity.freeze(preparation)
            parity.stage(preparation, run)
            sender_calls = []

            def sender(endpoint, wire, key, **kwargs):
                sender_calls.append(endpoint)
                provider = 'jev-coreinfra' if endpoint.endswith('/systemone') else 'luna-decision-coreinfra'
                connection = FakeConnection(body=encoded(response(provider)).encode())
                return post(endpoint, wire, key, **kwargs, connection_factory=lambda _: connection, sleep=lambda _: None)

            self.assertTrue(parity.execute(preparation, run, sender=sender)['validated'])
            self.assertEqual(sender_calls, [])
            staged = parity.score(preparation, run)
            self.assertEqual(staged['captured_response_rows'], 0)
            self.assertTrue(all(v['axis_match_delta'] is None for v in staged['comparison_to_prior'].values()))
            with patch.dict('os.environ', COREINFRA_API_KEY='synthetic-test-key'):
                parity.execute(preparation, run, live=True, sender=sender)
                with self.assertRaises(ValueError):
                    parity.execute(preparation, run, live=True, sender=sender)
            self.assertEqual(len(sender_calls), 16)
            report = parity.score(preparation, run)
            self.assertTrue(report['transport_evidence']['transport_verified'])
            self.assertTrue(report['transport_evidence']['native_contract_valid'])
            self.assertTrue(all(p['native_valid'] == 8 for p in report['providers'].values()))
            self.assertFalse(report['automatic_fact_acceptance'])
            rows_path = run / 'responses.jsonl'
            rows = [decode(line) for line in rows_path.read_bytes().splitlines()]
            rows[0]['wire_sha256'] = '0' * 64
            rows_path.write_text(''.join(encoded(r) + '\n' for r in rows))
            binding_path = run / 'execution-binding.json'
            binding = decode(binding_path.read_bytes())
            binding['file_sha256']['responses.jsonl'] = sha(rows_path.read_bytes())
            binding_path.write_text(encoded(binding))
            with self.assertRaisesRegex(ValueError, 'scheduled successful request'):
                inspect(preparation, run)

    def test_delta_counts_gains_losses_and_conflicts_without_truth_claim(self):
        rows, requests, references = fixture()
        old = parity.previous.summarize(rows, requests, references)
        changed = copy.deepcopy(rows)
        changed[0]['prediction']['labels']['concern_kind'] = 'mechanics'
        changed[0]['consistency_violations'] = ['conflict']
        changed[0]['status'] = 'needs_review'
        current = parity.previous.summarize(changed, requests, references)
        delta = parity.compare_prior(current, old)['fixture']
        self.assertEqual((delta['gains'], delta['losses'], delta['axis_match_delta']), (0, 1, -1))
        self.assertEqual((delta['before_coherent'], delta['after_coherent']), (2, 1))
        reverse = parity.compare_prior(old, current)['fixture']
        self.assertEqual((reverse['gains'], reverse['losses'], reverse['axis_match_delta']), (1, 0, 1))


if __name__ == '__main__':
    unittest.main()
