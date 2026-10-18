from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coreinfra_retry_run import decode, sha
from coreinfra_transport import post
import sol_top_line_comparison_v1 as comparison
from retrieval_index_v1.source import encoded
from test_coreinfra_transport import FakeConnection
from test_retrieval_fact_adapter_v1 import response

LABELS = dict(concern_kind='policy', evidence_confidence='supported', ownership='unknown', tool_responsibility='unknown')


def portable_comparison(report):
    # Analysis-host diagnostics may vary; frozen execution inventories must not.
    import copy
    result = copy.deepcopy(report)
    evidence = result['transport_evidence']
    evidence.pop('analysis_runtime_inventory', None)
    evidence.pop('analysis_runtime_matches_execution', None)
    for row in evidence.get('rows', []):
        row.pop('adapter_producer_sha256', None)
    return result


def fixture():
    requests = [dict(request_id=arm, provider='fixture', case_id='C', arm=arm) for arm in ('baseline', 'retrieval')]
    rows = [dict(r, native_status='valid', status='proposed_not_accepted', consistency_violations=[],
        prediction=dict(labels=dict(LABELS), warnings=[]), response_sha256='a' * 64) for r in requests]
    return rows, requests, {('C', arm): dict(LABELS) for arm in ('baseline', 'retrieval')}


class SolComparisonTests(unittest.TestCase):
    def test_portable_replay_retains_execution_evidence_and_labels(self):
        import copy
        original = dict(transport_evidence=dict(analysis_runtime_inventory={'host': 'local'},
            analysis_runtime_matches_execution=True, recorded_execution_runtime_inventory={'host': 'captured'},
            rows=[dict(adapter_producer_sha256={'host': 'local'}, wire_sha256='wire', prediction={'label': 'policy'})]))
        remote = copy.deepcopy(original)
        remote['transport_evidence']['analysis_runtime_inventory'] = {'host': 'CI'}
        remote['transport_evidence']['analysis_runtime_matches_execution'] = False
        remote['transport_evidence']['rows'][0]['adapter_producer_sha256'] = {'host': 'CI'}
        self.assertEqual(portable_comparison(original), portable_comparison(remote))
        for field in ('recorded_execution_runtime_inventory', 'rows'):
            changed = copy.deepcopy(remote)
            changed['transport_evidence'][field] = []
            self.assertNotEqual(portable_comparison(original), portable_comparison(changed))

    def test_recorded_live_comparison_reconstructs_without_network(self):
        run = comparison.ROOT / 'runs/2026-10-18-jev-luna-sol-comparison-v1'
        result = comparison.score(run)
        self.assertEqual(portable_comparison(result), portable_comparison(decode((run / 'comparison.json').read_bytes())))
        self.assertTrue(result['transport_evidence']['operationally_complete'])
        self.assertTrue(result['transport_evidence']['native_contract_valid'])
        jev = result['providers']['jev-coreinfra']
        luna = result['providers']['luna-decision-coreinfra']
        self.assertEqual((jev['all_axis_matches'], jev['primary_axis_matches'], jev['consistency_review']), (25, 15, 5))
        self.assertEqual((luna['all_axis_matches'], luna['primary_axis_matches'], luna['consistency_review']), (15, 7, 1))
        receipt = decode((run / 'result-receipt.json').read_bytes())
        files = {str(p.relative_to(run)): sha(p.read_bytes()) for p in run.rglob('*')
                 if p.is_file() and p != run / 'result-receipt.json'}
        self.assertEqual(receipt, dict(contract='specmetrics.sol-comparison-result/v1', status='complete',
            file_sha256=files, comparison_contract_receipt_sha256=sha((comparison.FROZEN / 'receipt.json').read_bytes()),
            producer_sha256=comparison.producers(), semantic_accuracy=None, automatic_fact_acceptance=False))

    def test_unknown_agreement_is_counted_without_fact_or_accuracy_authority(self):
        result = comparison.summarize(*fixture())['fixture']
        self.assertEqual(result['all_axis_matches'], 8)
        self.assertEqual(result['primary_axis_matches'], 4)
        self.assertEqual(result['paired_all_axis_match_delta'], 0)
        policy = comparison.policy()
        self.assertIsNone(policy['semantic_accuracy'])
        self.assertFalse(policy['H1_H2_eligibility'])

    def test_missing_invalid_and_conflicting_rows_keep_coverage_visible(self):
        for kind in ('missing', 'invalid', 'incoherent'):
            rows, requests, refs = fixture()
            if kind == 'missing':
                rows.pop()
            elif kind == 'invalid':
                rows[1].update(native_status='invalid', prediction=None)
            else:
                rows[1].update(status='needs_review', consistency_violations=['synthetic_conflict'])
            result = comparison.summarize(rows, requests, refs)['fixture']
            self.assertEqual(result['planned_axis_slots'], 8)
            if kind != 'incoherent':
                self.assertEqual(result['compared_axis_slots'], 4)
                self.assertIsNone(result['paired_all_axis_match_delta'])
            else:
                self.assertEqual(result['consistency_review'], 1)
                self.assertEqual(result['details'][1]['consistency_violations'], ['synthetic_conflict'])

    def test_positive_and_negative_pair_deltas_are_preserved(self):
        for arm, expected in [('baseline', 1), ('retrieval', -1)]:
            rows, requests, refs = fixture()
            next(r for r in rows if r['arm'] == arm)['prediction']['labels']['concern_kind'] = 'mechanics'
            result = comparison.summarize(rows, requests, refs)['fixture']
            self.assertEqual(result['paired_all_axis_match_delta'], expected)
            self.assertEqual(sum(bool(d['differing_axes']) for d in result['details']), 1)

    def test_duplicate_and_cross_case_responses_fail(self):
        rows, requests, refs = fixture()
        with self.assertRaises(ValueError):
            comparison.summarize(rows + [rows[0]], requests, refs)
        rows[0]['case_id'] = 'other'
        with self.assertRaises(ValueError):
            comparison.summarize(rows, requests, refs)

    def test_checksum_rebinding_cannot_change_comparator_or_denominators(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'contract'
            comparison.freeze(output)
            path = output / 'contract.json'
            value = decode(path.read_bytes())
            value['sol_top_line_sha256'] = '0' * 64
            path.write_text(encoded(value))
            receipt_path = output / 'receipt.json'
            receipt = decode(receipt_path.read_bytes())
            receipt['file_sha256']['contract.json'] = sha(path.read_bytes())
            receipt_path.write_text(encoded(receipt))
            with self.assertRaises(ValueError):
                comparison.verify_contract(output)

    def test_inspector_chain_uses_verified_responses_and_offline_staging_sends_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            contract, run = Path(directory) / 'contract', Path(directory) / 'run'
            comparison.freeze(contract)
            with patch.object(comparison, 'FROZEN', contract):
                comparison.prepare_run(run)
                staged = comparison.score(run)
                self.assertEqual(staged['captured_response_rows'], 0)
                self.assertFalse(staged['transport_evidence']['transport_verified'])
                def sender(endpoint, wire, key, **kwargs):
                    provider = 'jev-coreinfra' if endpoint.endswith('/systemone') else 'luna-decision-coreinfra'
                    connection = FakeConnection(body=encoded(response(provider)).encode())
                    return post(endpoint, wire, key, **kwargs, connection_factory=lambda _: connection, sleep=lambda _: None)
                with patch.dict('os.environ', COREINFRA_API_KEY='synthetic-unit-test-key'):
                    comparison.execute_transport(comparison.PREPARATION, run, live=True, sender=sender)
                result = comparison.score(run)
                self.assertEqual(result['captured_response_rows'], 16)
                self.assertTrue(result['transport_evidence']['transport_verified'])
                self.assertTrue(all(r['native_valid'] == 8 for r in result['providers'].values()))
                self.assertIsNone(result['semantic_accuracy'])
                self.assertFalse(result['automatic_fact_acceptance'])


def load_tests(loader, tests, pattern):
    if pattern is None:
        tests.addTests(loader.loadTestsFromName('test_sol_top_line_comparison_v2'))
    return tests


if __name__ == '__main__':
    unittest.main()
