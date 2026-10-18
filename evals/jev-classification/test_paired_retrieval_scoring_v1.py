import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coreinfra_retry_run import decode, sha
from coreinfra_transport import post
from paired_retrieval_execution_v1 import execute
import paired_retrieval_scoring_v1 as scoring
from paired_retrieval_study_v1 import stage
from retrieval_index_v1.source import encoded
from test_coreinfra_transport import FakeConnection
from test_retrieval_fact_adapter_v1 import response

UNKNOWN = dict(concern_kind='unknown', evidence_confidence='insufficient', ownership='unknown', tool_responsibility='unknown')
POLICY = dict(UNKNOWN, concern_kind='policy', evidence_confidence='supported')


def fixture(baseline=POLICY, retrieval=POLICY, truth_baseline=POLICY, truth_retrieval=POLICY):
    requests = [dict(request_id='C-' + a, provider='fixture', case_id='C', arm=a)
                for a in ('baseline', 'retrieval')]
    rows = [dict(r, native_status='valid', status='proposed_not_accepted', prediction=dict(labels=dict(labels)))
            for r, labels in zip(requests, (baseline, retrieval))]
    return rows, requests, {('C', 'baseline'): dict(truth_baseline), ('C', 'retrieval'): dict(truth_retrieval)}


class ScoringTests(unittest.TestCase):
    def summarize(self, args, qualified=True):
        return scoring.summarize(*args, qualified=qualified)['fixture']

    def test_unknown_is_agreement_but_not_ownership_resolution(self):
        result = self.summarize(fixture())
        self.assertEqual((result['diagnostic_label_matches'], result['compared_diagnostic_axis_slots']), (8, 8))
        self.assertEqual(result['H1']['net_supported_fact_resolutions'], 0)
        self.assertEqual(result['paired_resolution_details'][0]['role_owner_resolutions']['baseline'], (1, 0))
        self.assertEqual(result['H2']['new_unsupported_ownership_assertions'], 0)

    def test_justified_abstention_can_match_while_retrieval_adds_two_supported_resolutions(self):
        known = dict(POLICY, ownership='existing_specification')
        result = self.summarize(fixture(UNKNOWN, known, UNKNOWN, known))
        self.assertEqual(result['diagnostic_label_matches'], 8)
        self.assertEqual((result['H1']['gains'], result['H1']['losses']), (2, 0))
        self.assertEqual(result['H1']['mean_net_resolutions_per_pair'], 2)
        self.assertEqual(result['H1']['target_pair_denominator'], 1)

    def test_limited_support_no_resolutions_and_zero_denominator_is_not_zero_accuracy(self):
        limited = dict(POLICY, evidence_confidence='limited')
        result = self.summarize(fixture(limited, limited, limited, limited))
        self.assertEqual(result['H1']['status'], 'not_evaluable_no_supported_reference_resolutions')
        self.assertIsNone(result['H1']['mean_net_resolutions_per_pair'])

    def test_missing_invalid_and_incoherent_rows_keep_planned_denominators(self):
        original = fixture()
        for kind in ('missing', 'invalid', 'incoherent'):
            rows, requests, refs = copy.deepcopy(original)
            if kind == 'missing':
                rows.pop()
            elif kind == 'invalid':
                rows[1].update(native_status='invalid', prediction=None, status='rejected')
            else:
                rows[1]['status'] = 'needs_review'
            result = self.summarize((rows, requests, refs))
            self.assertEqual((result['planned_responses'], result['planned_axis_slots']), (2, 8))
            self.assertEqual(result['H1']['status'], 'not_evaluable_incomplete_or_incoherent_responses')
            self.assertEqual(result['diagnostic_label_mismatches'], 0)

    def test_new_unsupported_owner_fails_H2_and_existing_unsupported_claim_stays_visible(self):
        claimed = dict(POLICY, ownership='existing_specification')
        result = self.summarize(fixture(POLICY, claimed))
        self.assertEqual(result['H2']['new_unsupported_ownership_assertions'], 1)
        result = self.summarize(fixture(claimed, claimed))
        self.assertEqual(result['H2']['new_unsupported_ownership_assertions'], 0)
        self.assertTrue(all(result['paired_resolution_details'][0]['unsupported_ownership'].values()))
        other = dict(POLICY, ownership='simple_composition')
        self.assertEqual(self.summarize(fixture(claimed, other))['H2']['new_unsupported_ownership_assertions'], 1)

    def test_unqualified_diagnostic_agreement_cannot_claim_hypothesis_success(self):
        result = self.summarize(fixture(), qualified=False)
        self.assertEqual(result['diagnostic_label_matches'], 8)
        self.assertEqual(result['H1']['status'], 'not_evaluable_reference_design')
        self.assertEqual(result['H2']['status'], 'not_evaluable_reference_design')

    def test_duplicate_or_cross_target_response_and_conflicting_qualified_reference_are_rejected(self):
        rows, requests, refs = fixture()
        with self.assertRaises(ValueError):
            self.summarize((rows + [rows[0]], requests, refs))
        rows[0]['case_id'] = 'other'
        with self.assertRaises(ValueError):
            self.summarize((rows, requests, refs))
        conflicting = dict(POLICY, concern_kind='mechanics')
        with self.assertRaisesRegex(ValueError, 'conflicting reference'):
            self.summarize(fixture(truth_retrieval=conflicting))

    def test_contract_cannot_be_rebound_to_change_unknown_or_denominator_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'contract'
            scoring.freeze(output)
            path = output / 'contract.json'
            value = decode(path.read_bytes())
            value['planned_responses'] = 15
            path.write_text(encoded(value))
            receipt_path = output / 'receipt.json'
            receipt = decode(receipt_path.read_bytes())
            receipt['file_sha256']['contract.json'] = sha(path.read_bytes())
            receipt_path.write_text(encoded(receipt))
            with self.assertRaises(ValueError):
                scoring.verify_contract(output)

    def test_real_inspector_chain_can_pass_H3_but_cannot_score_H1_H2_on_current_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            contract, run = Path(directory) / 'contract', Path(directory) / 'run'
            scoring.freeze(contract)
            stage(scoring.PREPARATION, run)
            with patch.object(scoring, 'FROZEN', contract):
                staged = scoring.score(run)
                self.assertEqual(staged['H3']['status'], 'not_evaluable_incomplete_evidence')
                self.assertEqual(sum(p['verified_rows_available'] for p in staged['providers'].values()), 0)
                def sender(endpoint, wire, key, **kwargs):
                    provider = 'jev-coreinfra' if endpoint.endswith('/systemone') else 'luna-decision-coreinfra'
                    connection = FakeConnection(body=encoded(response(provider)).encode())
                    return post(endpoint, wire, key, **kwargs, connection_factory=lambda _: connection, sleep=lambda _: None)
                with patch.dict('os.environ', COREINFRA_API_KEY='synthetic-unit-test-key'):
                    execute(scoring.PREPARATION, run, live=True, sender=sender)
                report = scoring.score(run)
                self.assertEqual(report['H3']['status'], 'passes_pilot')
                self.assertFalse(report['paired_quality_scoring_allowed'])
                self.assertEqual(sum(p['planned_responses'] for p in report['providers'].values()), 16)
                for provider in report['providers'].values():
                    self.assertEqual((provider['planned_responses'], provider['native_valid']), (8, 8))
                    self.assertEqual(provider['H1']['status'], 'not_evaluable_reference_design')
                    self.assertEqual(provider['H2']['status'], 'not_evaluable_reference_design')


if __name__ == '__main__':
    unittest.main()
