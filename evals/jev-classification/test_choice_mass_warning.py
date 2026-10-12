import copy
from decimal import Decimal
import unittest

from coreinfra_retry_run import decode
from decision_choice_contract import parse_response as strict_parse
from decision_choice_contract_v2 import ChoiceContractError, POLICY, parse_response
from question_grouping import canonical
from score_contrastive_decisions_v2 import delta_interval
from test_contrastive_decision_study import QUESTIONS, REFERENCE, RUN, response_for


def body_for(total='0.99', *, luna=False, extra_options=False, axis='concern_kind'):
    packet = decode((REFERENCE / 'case-packet.json').read_bytes())
    body = response_for(canonical({'model': 'gpt-6-luna' if luna else 'jev-1.13.0',
                                  'state': canonical(packet['cases'][0]['state']).decode()}))
    q = copy.deepcopy(QUESTIONS)
    labels = list(q[axis]['criteria'])
    if extra_options:
        q[axis]['criteria']['fifth'] = 'fifth'
        labels.append('fifth')
    answer = body['answers'][axis]
    answer['choice'] = labels[0]
    answer['probabilities'] = {label: 0.0 for label in labels}
    answer['probabilities'][labels[0]] = 0.9
    answer['probabilities'][labels[1]] = float(Decimal(total) - Decimal('.9'))
    if luna:
        body['answers'] = [{**a, 'name': axis,
                           'probabilities': [{'value': k, 'probability': v} for k, v in a['probabilities'].items()]}
                          for axis, a in body['answers'].items()]
    return body, q


def parse(body, questions=QUESTIONS, provider='jev-coreinfra', model='jev-1.13.0'):
    return parse_response(canonical(body), provider=provider, model=model, questions=questions)


class MassAllowance(unittest.TestCase):
    def test_inclusive_decimal_boundaries_preserve_raw_numbers_and_confidence(self):
        for axis in QUESTIONS:
            for total in ('0.99', '1.01', '0.999', '1.001'):
                with self.subTest(total=total, axis=axis):
                    body, q = body_for(total, axis=axis)
                    result = parse(body, q)
                    self.assertEqual(result['answers'], body['answers'])
                    self.assertEqual(result['warnings'], [{'code': 'probability_mass_deviation',
                        'axis': axis, 'policy': POLICY, 'raw_total': str(Decimal(total)),
                        'residual': str(Decimal(total) - 1), 'absolute_allowance': '0.01'}])

    def test_outside_boundaries_rejected_and_small_numeric_noise_has_no_warning(self):
        for total in ('0.989999', '1.010001', '0.98', '1.02'):
            with self.subTest(total=total):
                body, q = body_for(total)
                with self.assertRaisesRegex(ChoiceContractError, 'probability_mass_outside_allowance'):
                    parse(body, q)
        for total in ('1', '0.999999', '1.000001'):
            body, q = body_for(total)
            self.assertEqual(parse(body, q)['warnings'], [])

    def test_allowance_not_transferred_to_luna_other_models_or_larger_taxonomies(self):
        body, q = body_for(luna=True)
        with self.assertRaises(ChoiceContractError):
            parse(body, q, 'luna-decision-coreinfra', 'gpt-6-luna')
        body, q = body_for(); body['model'] = 'jev-future'
        with self.assertRaises(ChoiceContractError):
            parse(body, q, model='jev-future')
        body, q = body_for(extra_options=True)
        with self.assertRaises(ChoiceContractError):
            parse(body, q)

    def test_structural_numeric_and_winner_failures_are_not_rescued(self):
        mutations = [lambda b: b['answers']['concern_kind'].update(choice='missing'),
                     lambda b: b['answers']['concern_kind'].update(choice=list(QUESTIONS['concern_kind']['criteria'])[1]),
                     lambda b: b['answers']['concern_kind'].update(confidence=True),
                     lambda b: b['answers']['concern_kind'].update(type='score'),
                     lambda b: b['answers']['concern_kind']['probabilities'].pop(next(iter(QUESTIONS['concern_kind']['criteria']))),
                     lambda b: b['answers']['concern_kind']['probabilities'].update(extra=0)]
        for value in (True, '0.1', float('nan'), float('inf'), -0.01, 1.01):
            mutations.append(lambda b, value=value: b['answers']['concern_kind']['probabilities'].update(
                {next(iter(QUESTIONS['concern_kind']['criteria'])): value}))
        for mutation in mutations:
            body, q = body_for(); mutation(body)
            with self.subTest(mutation=mutation), self.assertRaises(ChoiceContractError):
                parse(body, q)

    def test_real_sum_only_failure_accepted_by_v2_and_still_rejected_by_v1(self):
        rows = [decode(line) for line in (RUN / 'responses.jsonl').read_bytes().splitlines()]
        body = next(r['response'] for r in rows if r['request_id'] == 'r2-case-10-jev-coreinfra')
        result = parse(body)
        self.assertEqual(result['answers'], body['answers'])
        self.assertEqual(result['warnings'][0]['raw_total'], '0.99')
        with self.assertRaisesRegex(ValueError, 'Distribution is not normalized'):
            strict_parse(canonical(body), provider='jev-coreinfra', model='jev-1.13.0', questions=QUESTIONS)

    def test_interval_touching_zero_is_unresolved_and_large_margin_is_robust(self):
        self.assertEqual(delta_interval(.49, .50)['direction'], 'unresolved')
        self.assertEqual(delta_interval(.49, .501)['direction'], 'positive')
        self.assertEqual(delta_interval(.50, .49)['direction'], 'unresolved')
        self.assertEqual(delta_interval(0, 1)['lower'], '0.990')
        self.assertEqual(delta_interval(1, 0)['direction'], 'negative')


if __name__ == '__main__':
    unittest.main()
