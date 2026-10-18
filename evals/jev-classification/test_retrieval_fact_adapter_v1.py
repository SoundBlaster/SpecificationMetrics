import copy
import hashlib
import io
import itertools
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from adapt_retrieval_facts_v1 import main
from decision_choice_contract_v2 import ChoiceContractError, ResponseIdentityError
from prepare_retrieval_context_v1 import PROVIDERS, QUESTIONS, prepare, wire, write_bundle
from recommendation_policy_v1.context import Facts
from recommendation_policy_v1.proposals import fingerprint, questions
from retrieval_fact_adapter_v1 import adapt_response
from retrieval_fact_adapter_v1.native import parse_response
from retrieval_index_v1.source import digest, encoded
from test_retrieval_context_v1 import Encoder
from test_retrieval_index_v1 import CODE

DEFAULT = dict(concern_kind='unknown', evidence_confidence='insufficient',
               ownership='unknown', tool_responsibility='unknown')


def response(provider='jev-coreinfra', labels=None):
    labels = DEFAULT if labels is None else labels
    answers = {axis: dict(type='choice', choice=labels[axis], confidence=.87,
                          probabilities={k: float(k == labels[axis]) for k in q['criteria']})
               for axis, q in QUESTIONS.items()}
    if provider == 'luna-decision-coreinfra':
        answers = [dict(a, name=axis, probabilities=[dict(value=k, probability=p)
                    for k, p in a['probabilities'].items()]) for axis, a in answers.items()]
    return dict(model=PROVIDERS[provider][0], answers=answers)


def raw(body):
    return json.dumps(body).encode()


class NativeContractTests(unittest.TestCase):
    def parse(self, body, provider='jev-coreinfra'):
        return parse_response(raw(body), provider=provider, model=PROVIDERS[provider][0])

    def test_both_envelopes_preserve_labels_numbers_and_support_axis(self):
        for provider in PROVIDERS:
            result = self.parse(response(provider), provider)
            self.assertEqual(result['labels'], DEFAULT)
            self.assertEqual(result['answers']['evidence_confidence']['choice'], 'insufficient')
            self.assertEqual(result['answers']['evidence_confidence']['provider_confidence'], .87)
            self.assertEqual(result['warnings'], [])

    def test_wrong_models_and_old_three_axis_answers_are_identity_errors(self):
        for provider in PROVIDERS:
            body = response(provider)
            body['model'] = 'other-model'
            with self.assertRaises(ResponseIdentityError):
                self.parse(body, provider)
        body = response()
        del body['answers']['ownership']
        del body['answers']['tool_responsibility']
        body['answers']['recommendation'] = {}
        with self.assertRaises(ResponseIdentityError):
            self.parse(body)
        with self.assertRaises(ResponseIdentityError):
            parse_response(raw(response()), provider='unknown', model='jev-1.13.0')

    def test_missing_extra_and_duplicate_question_or_option_identities(self):
        for axis in QUESTIONS:
            body = response()
            del body['answers'][axis]
            with self.subTest(axis=axis), self.assertRaises(ResponseIdentityError):
                self.parse(body)
        body = response()
        body['answers']['extra'] = {}
        with self.assertRaises(ResponseIdentityError):
            self.parse(body)
        body = response('luna-decision-coreinfra')
        body['answers'][1] = body['answers'][0]
        with self.assertRaises(ResponseIdentityError):
            self.parse(body, 'luna-decision-coreinfra')
        body = response('luna-decision-coreinfra')
        options = body['answers'][0]['probabilities']
        options[1] = options[0]
        with self.assertRaises(ChoiceContractError):
            self.parse(body, 'luna-decision-coreinfra')

    def test_duplicate_json_nonfinite_truncated_or_oversized_input_is_rejected(self):
        duplicate = raw(response()).replace(b'"answers":', b'"answers": {}, "answers":', 1)
        invalid = [b'{', b'\xff', duplicate, b'NaN', b'1e9999', b' ' * (1024 * 1024 + 1)]
        for value in invalid:
            with self.subTest(value=value[:40]), self.assertRaises(ChoiceContractError):
                parse_response(value, provider='jev-coreinfra', model='jev-1.13.0')

    def test_invalid_probabilities_confidence_choices_refusals_and_coverage(self):
        for field in ('probability', 'confidence'):
            for invalid in (True, None, '0.5', -0.1, 1.1, float('nan'), float('inf')):
                body = response()
                answer = body['answers']['concern_kind']
                if field == 'probability':
                    answer['probabilities']['unknown'] = invalid
                else:
                    answer['confidence'] = invalid
                with self.subTest(field=field, invalid=invalid), self.assertRaises(ChoiceContractError):
                    self.parse(body)
        for mutation in ('refusal', 'absent', 'not_maximum', 'coverage'):
            body = response()
            if mutation == 'refusal':
                body['answers']['ownership']['type'] = 'refusal'
            elif mutation == 'absent':
                body['answers']['ownership']['choice'] = 'absent_in_scope'
            elif mutation == 'not_maximum':
                body['answers']['concern_kind']['probabilities'].update(unknown=.4, policy=.6)
            else:
                del body['answers']['concern_kind']['probabilities']['policy']
            with self.subTest(mutation=mutation), self.assertRaises(ChoiceContractError):
                self.parse(body)

    def test_jev_mass_allowance_only_applies_to_three_or_four_choices(self):
        for axis in ('concern_kind', 'evidence_confidence', 'ownership'):
            for selected_mass, allowed in ((.99, True), (.989, False), (.999999, True)):
                body = response()
                choice = body['answers'][axis]['choice']
                body['answers'][axis]['probabilities'][choice] = selected_mass
                if allowed:
                    result = self.parse(body)
                    self.assertEqual(result['answers'][axis]['probabilities'][choice], selected_mass)
                    self.assertEqual(len(result['warnings']), int(selected_mass == .99))
                else:
                    with self.assertRaisesRegex(ChoiceContractError, 'mass'):
                        self.parse(body)
        for provider in PROVIDERS:
            body = response(provider)
            if provider == 'jev-coreinfra':
                body['answers']['tool_responsibility']['probabilities']['unknown'] = .99
            else:
                body['answers'][0]['probabilities'][-1]['probability'] = .99
            with self.assertRaisesRegex(ChoiceContractError, 'mass'):
                self.parse(body, provider)


class AdaptationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        def git(*args):
            subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True)
        git('init', '-q')
        git('config', 'user.name', 'Adapter fixture')
        git('config', 'user.email', 'adapter@example.invalid')
        (self.repo / 'tools').mkdir()
        (self.repo / 'tools/policy.py').write_text(CODE)
        git('add', '-A')
        git('commit', '-qm', 'fixture')
        self.packet = prepare(self.repo, 'fixture', 'HEAD', ('tools/*.py',), (), self.root / 'index.sqlite',
                              Encoder(), 'tools/policy.py::allowed', 'Find a rule for positive values')
        self.bundle = self.root / 'bundle'
        write_bundle(self.bundle, self.packet)

    def test_valid_proposals_are_bound_and_do_not_mutate_preparation(self):
        before = {p.name: p.read_bytes() for p in self.bundle.iterdir()}
        labels = dict(DEFAULT, concern_kind='policy', evidence_confidence='supported',
                      ownership='existing_specification')
        for provider in PROVIDERS:
            value = raw(response(provider, labels))
            report = adapt_response(self.bundle, provider, value)
            request = next(r for r in self.packet['requests'] if r['provider'] == provider)
            self.assertEqual(report['status'], 'proposed_not_accepted')
            self.assertEqual(report['wire_sha256'], request['wire_sha256'])
            self.assertEqual(report['response_sha256'], hashlib.sha256(value).hexdigest())
            self.assertEqual(report['facts_sha256'], self.packet['fact_plan']['facts_sha256'])
            self.assertEqual(report['proposed_facts']['ownership'], 'existing_specification')
            for field in ('automatic_fact_acceptance', 'write_authority', 'transport_verified',
                          'source_locators_verified', 'rich_proposal_compatible', 'semantic_correctness_verified'):
                self.assertIs(report[field], False)
            self.assertNotIn('source_locators', report['proposed_facts'])
            self.assertTrue(all(e['outcome'] == 'satisfied' for e in report['consistency_trace']))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.bundle.iterdir()})

    def test_all_72_label_combinations_preserve_conflicts_for_review(self):
        counts = {'proposed_not_accepted': 0, 'needs_review': 0}
        for values in itertools.product(*(q['criteria'] for q in QUESTIONS.values())):
            labels = dict(zip(QUESTIONS, values))
            report = adapt_response(self.bundle, 'jev-coreinfra', raw(response(labels=labels)))
            counts[report['status']] += 1
            self.assertEqual(report['prediction']['labels'], labels)
            consistent = ((labels['concern_kind'] == 'unknown') ==
                          (labels['evidence_confidence'] == 'insufficient'))
            overlap = labels['ownership'] != 'unknown' and labels['tool_responsibility'] == 'yes'
            self.assertEqual(report['status'] == 'proposed_not_accepted', consistent and not overlap)
            self.assertEqual(report['proposed_facts'] is None, not consistent or overlap)
            self.assertEqual([e['name'] for e in report['consistency_trace']],
                             ['RoleSupportConsistentSpec', 'ResponsibilitiesCompatibleSpec'])
        self.assertEqual(counts, {'proposed_not_accepted': 28, 'needs_review': 44})

    def test_invalid_native_shape_is_distinct_from_inconsistent_valid_tuple(self):
        report = adapt_response(self.bundle, 'jev-coreinfra', b'{}')
        self.assertEqual((report['status'], report['native_status']), ('rejected', 'invalid'))
        self.assertTrue(report['stop_required'])
        self.assertEqual(report['consistency_trace'], [])
        labels = dict(DEFAULT, concern_kind='policy')
        report = adapt_response(self.bundle, 'jev-coreinfra', raw(response(labels=labels)))
        self.assertEqual((report['status'], report['native_status']), ('needs_review', 'valid'))
        self.assertFalse(report['stop_required'])
        self.assertIn('unknown_requires_insufficient_and_vice_versa', report['consistency_violations'])

    def test_bad_receipt_wrong_fact_snapshot_and_known_fields_fail_before_adaptation(self):
        receipt = self.bundle / 'preparation-receipt.json'
        original = receipt.read_bytes()
        receipt.write_text('{}')
        with self.assertRaises(ValueError):
            adapt_response(self.bundle, 'jev-coreinfra', raw(response()))
        receipt.write_bytes(original)
        packet = copy.deepcopy(self.packet)
        packet['fact_plan']['facts_sha256'] = '0' * 64
        stale = self.root / 'stale'
        write_bundle(stale, packet)
        with self.assertRaisesRegex(ValueError, 'fact plan'):
            adapt_response(stale, 'jev-coreinfra', raw(response()))
        packet = copy.deepcopy(self.packet)
        packet['state']['accepted_facts']['role'].update(kind='policy', support='supported')
        packet['fact_plan']['accepted_facts'] = packet['state']['accepted_facts']
        facts = Facts.model_validate_json(encoded(packet['state']['accepted_facts']))
        packet['fact_plan']['facts_sha256'] = fingerprint(facts)
        packet['fact_plan']['questions'] = questions(facts)
        packet['state_sha256'] = digest(encoded(packet['state']))
        packet['requests'] = [wire(p, encoded(packet['state'])) for p in PROVIDERS]
        known = self.root / 'known'
        write_bundle(known, packet)
        with self.assertRaisesRegex(ValueError, 'fact plan'):
            adapt_response(known, 'jev-coreinfra', raw(response()))

    def test_cli_writes_new_report_and_rejects_overwrite_without_network(self):
        response_file, output = self.root / 'response.json', self.root / 'adapted.json'
        response_file.write_bytes(raw(response()))
        args = ['adapter', '--preparation', str(self.bundle), '--provider', 'jev-coreinfra',
                '--response', str(response_file), '--output', str(output)]
        with patch('sys.argv', args), patch('coreinfra_transport.post', side_effect=AssertionError('no network')):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
            report = json.loads(output.read_text())
            self.assertEqual(report['hosted_requests_by_adapter'], 0)
            with patch('sys.stderr', io.StringIO()), self.assertRaises(SystemExit):
                main()
        self.assertEqual(raw(response()), response_file.read_bytes())

    def test_cli_review_and_rejection_results_use_exit_two_and_keep_raw_file(self):
        response_file = self.root / 'response.json'
        variants = [('review', raw(response(labels=dict(DEFAULT, concern_kind='policy'))), 'needs_review'),
                    ('invalid', b'{}', 'rejected')]
        for name, value, status in variants:
            response_file.write_bytes(value)
            output = self.root / (name + '.json')
            args = ['adapter', '--preparation', str(self.bundle), '--provider', 'jev-coreinfra',
                    '--response', str(response_file), '--output', str(output)]
            with patch('sys.argv', args), redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 2)
            self.assertEqual(json.loads(output.read_text())['status'], status)
            self.assertEqual(response_file.read_bytes(), value)


if __name__ == '__main__':
    unittest.main()
