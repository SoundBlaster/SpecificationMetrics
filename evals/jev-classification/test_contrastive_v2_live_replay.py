"""Replay the completed v2 provider evidence offline, without another POST."""
from collections import Counter
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch

from contrastive_decision_study import RUN as V1_RUN
from contrastive_decision_study_v2 import inspect_results
from coreinfra_retry_run import decode
from decision_choice_contract import parse_response as strict_parse
from question_grouping import canonical, digest
from score_contrastive_decisions_v2 import score

RUN = Path(__file__).parent / 'runs/2026-10-13-contrastive-warning-v2'


def read(name):
    return decode((RUN / name).read_bytes())


class CompletedLiveReplay(unittest.TestCase):
    def test_native_and_semantic_reports_replay_without_credentials(self):
        with patch('contrastive_decision_study_v2.os.environ') as env, patch(
                'coreinfra_transport.http.client.HTTPSConnection',
                side_effect=AssertionError('Offline replay must not open HTTPS')):
            env.get.side_effect = AssertionError('Offline replay must not read a key')
            self.assertEqual(inspect_results(RUN), read('native-validation.json'))
            self.assertEqual(score(RUN), read('score.json'))
        receipt = read('receipt.json')
        self.assertTrue(receipt['completed'])
        self.assertIsNone(receipt['stop_reason'])
        self.assertEqual((receipt['attempted_requests'], receipt['network_attempts'], receipt['potentially_billable_posts']),
                         (48, 48, 48))
        self.assertEqual((receipt['warned_responses'], receipt['native_invalid_responses'], receipt['ambiguous_posts']), (0, 0, 0))
        native = read('native-validation.json')
        self.assertTrue(native['execution_complete'])
        self.assertTrue(native['operationally_complete'])
        self.assertEqual(native['missing_result_request_ids'], [])

    def test_warning_path_not_exercised_all_live_responses_also_pass_v1_strict_decoder(self):
        manifest = read('manifest.json')
        requests = {r['request_id']: r for r in manifest['requests']}
        questions = decode(manifest['requests'][0]['wire_json'])['questions']
        if isinstance(questions, list):
            questions = {q['name']: {'type': q['type'], 'instructions': q['instructions'],
                                     'criteria': {v['value']: v['description'] for v in q['choices']}}
                         for q in questions}
        rows = [decode(line) for line in (RUN / 'responses.jsonl').read_bytes().splitlines()]
        self.assertEqual(len(rows), 48)
        for row in rows:
            request = requests[row['request_id']]
            parsed = strict_parse(canonical(row['response']), provider=request['provider'],
                                  model=request['requested_model'], questions=questions)
            self.assertEqual(row['validation']['warnings'], [])
            self.assertEqual(row['validation']['status'], 'valid')
            self.assertEqual(parsed['model'], request['requested_model'])

    def test_role_distinction_and_withheld_abstention_remain_separate(self):
        result = read('score.json')
        expected = {'jev-coreinfra': ((4, 4), (2, 1)), 'luna-decision-coreinfra': ((3, 3), (3, 3))}
        controls = []
        for provider in result['providers']:
            h1, h2 = expected[provider['provider']]
            for index, repeat in enumerate(provider['repeats']):
                self.assertTrue(repeat['operationally_complete'])
                self.assertEqual(repeat['H1']['correct_pairs'], h1[index])
                self.assertEqual(repeat['H2']['correct_controls'], h2[index])
                self.assertFalse(repeat['H2']['supported'])
                self.assertTrue(repeat['H3_secondary']['supported'])
                self.assertEqual(repeat['H3_secondary']['directional_pairs'], 4)
                self.assertEqual(repeat['eligible_policy_recall']['recovered'], 4)
                controls.extend(repeat['withheld_controls'])
                if provider['provider'] == 'jev-coreinfra':
                    self.assertTrue(repeat['H1']['supported'])
                    for pair in repeat['pairs']:
                        self.assertTrue(pair['probability_sensitivity']['both_lower_bounds_positive'])
                        for bounds in pair['probability_sensitivity']['axes'].values():
                            self.assertGreaterEqual(Decimal(bounds['lower']), Decimal('.540'))
                else:
                    self.assertEqual(repeat['mechanical_false_positives']['case_ids'], ['case-10'])
        self.assertEqual(len(controls), 16)
        self.assertTrue(all(c['prediction']['answers']['opportunity']['choice'] == 'needs_review' for c in controls))

    def test_repeat_changes_are_localized_and_input_catalog_is_unchanged(self):
        result = read('score.json')
        providers = {p['provider']: p for p in result['providers']}
        self.assertEqual(providers['jev-coreinfra']['repeat_consistency']['label_disagreements'],
                         [{'case_id': 'case-03', 'axis': 'concern_kind', 'repeat_1': 'unknown', 'repeat_2': 'policy'}])
        self.assertFalse(providers['jev-coreinfra']['repeat_consistency']['supported'])
        self.assertTrue(providers['luna-decision-coreinfra']['repeat_consistency']['supported'])
        old = decode((V1_RUN / 'manifest.json').read_bytes())
        new = read('manifest.json')
        self.assertEqual(new['requests'], old['requests'])
        self.assertEqual(new['input_sha256'], old['input_sha256'])
        self.assertNotEqual(new['study'], old['study'])

    def test_accounting_hashes_and_reported_usage_match_raw_evidence(self):
        summary = read('analysis-summary.json')
        for name, expected in summary['evidence_sha256'].items():
            self.assertEqual(digest((RUN / name).read_bytes()), expected)
        requests = {r['request_id']: r for r in read('manifest.json')['requests']}
        usage = {}
        for line in (RUN / 'responses.jsonl').read_bytes().splitlines():
            row = decode(line)
            totals = usage.setdefault(requests[row['request_id']]['provider'], Counter())
            totals['responses_with_usage'] += 1
            totals.update({k: row['response']['usage'][k] for k in ('input_tokens', 'output_tokens')})
        self.assertEqual(usage, summary['reported_usage'])
        self.assertIsNone(summary['actual_billed_cost'])
        self.assertIsNone(summary['remaining_credential_balance'])
        self.assertEqual(summary['new_inference_requests_by_analysis'], 0)
        self.assertEqual(summary['metric_effect'], 'none')


if __name__ == '__main__':
    unittest.main()
