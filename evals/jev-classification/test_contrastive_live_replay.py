"""Replay the stopped real study offline; never request provider inference."""
from collections import Counter
from decimal import Decimal
from unittest.mock import patch
import unittest

from contrastive_decision_study import RUN, REFERENCE, inspect_results
from coreinfra_retry_run import decode
from decision_choice_contract import parse_response
from question_grouping import canonical, digest
from score_contrastive_decisions import score


def read(name):
    return decode((RUN / name).read_bytes())


class StoppedLiveReplay(unittest.TestCase):
    def test_saved_native_and_semantic_reports_replay_without_credentials_or_inference(self):
        with patch('contrastive_decision_study.os.environ') as env:
            env.get.side_effect = AssertionError('Offline replay must not read credentials')
            self.assertEqual(inspect_results(), read('native-validation.json'))
            self.assertEqual(score(), read('score.json'))
        result = read('score.json')
        self.assertEqual((result['planned_requests'], result['received_rows'], result['native_valid'], result['native_invalid']),
                         (48, 42, 41, 1))
        self.assertFalse(result['operationally_complete'])
        self.assertEqual(len(result['unattempted_request_ids']), 6)
        self.assertEqual(result['attempt_status_unknown_request_ids'], [])
        receipt = read('receipt.json')
        self.assertEqual(receipt['stop_reason'], 'native_contract_invalid')
        self.assertEqual((receipt['network_attempts'], receipt['potentially_billable_posts'], receipt['ambiguous_posts']),
                         (42, 42, 0))
        self.assertTrue(receipt['attempt_ledger_complete'])
        self.assertFalse(receipt['completed'])

    def test_real_invalid_distribution_stays_rejected_as_whole_response(self):
        raw = [decode(line) for line in (RUN / 'responses.jsonl').read_bytes().splitlines()]
        row = next(r for r in raw if r['request_id'] == 'r2-case-10-jev-coreinfra')
        answers = row['response']['answers']
        self.assertEqual(sum(Decimal(str(v)) for v in answers['concern_kind']['probabilities'].values()), Decimal('0.99'))
        self.assertEqual(sum(Decimal(str(v)) for v in answers['opportunity']['probabilities'].values()), Decimal(1))
        questions = decode((REFERENCE / 'case-packet.json').read_bytes())['questions']
        with self.assertRaisesRegex(ValueError, 'Distribution is not normalized'):
            parse_response(canonical(row['response']), provider='jev-coreinfra', model='jev-1.13.0', questions=questions)
        saved = next(r for r in read('native-validation.json')['rows'] if r['request_id'] == row['request_id'])
        self.assertEqual(saved['native_status'], 'invalid')
        self.assertIsNone(saved['prediction'])

    def test_complete_first_repeat_and_partial_second_remain_separate(self):
        result = read('score.json')
        expected = {'jev-coreinfra': (4, 1, 8), 'luna-decision-coreinfra': (3, 3, 9)}
        for provider in result['providers']:
            h1, h2, available = expected[provider['provider']]
            first, second = provider['repeats']
            self.assertTrue(first['operationally_complete'])
            self.assertEqual(first['H1']['correct_pairs'], h1)
            self.assertEqual(first['H2']['correct_controls'], h2)
            self.assertEqual(first['H3_secondary']['directional_pairs'], 4)
            self.assertTrue(first['H3_secondary']['supported'])
            self.assertFalse(second['operationally_complete'])
            self.assertEqual(second['usable_cases'], available)
            self.assertEqual(second['H1']['planned'], 4)
            self.assertEqual(second['H3_secondary']['planned'], 4)
            for hypothesis in ('H1', 'H2', 'H3_secondary'):
                self.assertFalse(second[hypothesis]['supported'])
            self.assertFalse(provider['repeat_consistency']['supported'])

    def test_all_withheld_eligibility_abstentions_do_not_mask_kind_errors(self):
        result = read('score.json')
        joint = {'jev-coreinfra': (1, 2), 'luna-decision-coreinfra': (3, 3)}
        controls = []
        for provider in result['providers']:
            for repeat, expected_joint in zip(provider['repeats'], joint[provider['provider']]):
                cases = repeat['withheld_controls']
                self.assertEqual(len(cases), 4)
                self.assertTrue(all(c['usable_for_criteria'] for c in cases))
                self.assertTrue(all(c['prediction']['answers']['opportunity']['choice'] == 'needs_review' for c in cases))
                self.assertEqual(sum(c['jointly_correct'] for c in cases), expected_joint)
                controls.extend(cases)
        self.assertEqual(len(controls), 16)
        jev, luna = result['providers']
        self.assertEqual(len(jev['repeat_consistency']['label_disagreements']), 1)
        self.assertEqual(luna['repeat_consistency']['label_disagreements'], [])
        self.assertEqual(luna['repeat_consistency']['paired_axis_answers'], 18)

    def test_diagnosis_usage_and_evidence_hashes_include_the_invalid_response(self):
        diagnosis, summary = read('native-contract-diagnosis.json'), read('usage-summary.json')
        self.assertEqual(diagnosis['manifest_sha256'], digest((RUN / 'manifest.json').read_bytes()))
        self.assertEqual(diagnosis['responses_sha256'], digest((RUN / 'responses.jsonl').read_bytes()))
        self.assertEqual(diagnosis['decimal_sum'], '0.99')
        self.assertFalse(diagnosis['whole_native_response_accepted'])
        self.assertEqual(diagnosis['rounding_hypothesis']['status'],
                         'numerically_compatible_not_provider_contract_or_root_cause_verified')
        self.assertTrue(diagnosis['rounding_hypothesis']['interval_contains_one'])
        for field, filename in (('manifest_sha256', 'manifest.json'), ('score_sha256', 'score.json'),
                                ('receipt_sha256', 'receipt.json'), ('native_validation_sha256', 'native-validation.json')):
            self.assertEqual(summary[field], digest((RUN / filename).read_bytes()))
        requests = {r['request_id']: r for r in read('manifest.json')['requests']}
        usage = {}
        for line in (RUN / 'responses.jsonl').read_bytes().splitlines():
            row = decode(line); provider = requests[row['request_id']]['provider']
            totals = usage.setdefault(provider, Counter())
            totals['responses_with_usage'] += 1
            totals.update({k: row['response']['usage'][k] for k in ('input_tokens', 'output_tokens')})
        self.assertEqual(usage, summary['reported_usage'])
        self.assertTrue(summary['usage_includes_native_invalid_response'])
        self.assertIsNone(summary['actual_billed_cost'])
        self.assertIsNone(summary['remaining_credential_balance'])


if __name__ == '__main__':
    unittest.main()
