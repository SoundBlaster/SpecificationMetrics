"""Native envelope/projection smoke tests; all HTTP and credentials are fake."""
import copy
import json
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest.mock import patch

from coreinfra_transport import post
from decision_choice_contract_v2 import ChoiceContractError
import intent_first_native_v1 as native
import prepare_intent_first_native as prep
from question_grouping import canonical, digest
from test_coreinfra_transport import FakeConnection


def response(provider='jev-coreinfra', labels=None):
    labels = labels or {'concern_kind': 'unknown', 'evidence_confidence': 'insufficient', 'recommendation': 'formalize'}
    answers = {axis: {'type': 'choice', 'choice': labels[axis], 'confidence': .87,
                      'probabilities': {k: float(k == labels[axis]) for k in question['criteria']}}
               for axis, question in native.QUESTIONS.items()}
    if provider == 'luna-decision-coreinfra':
        answers = [{**a, 'name': axis, 'probabilities': [{'value': k, 'probability': v}
                                                       for k, v in a['probabilities'].items()]}
                   for axis, a in answers.items()]
    return {'model': native.PROVIDERS[provider][0], 'answers': answers}


class NativePreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = prep.build()
        cls.manifest = json.loads(cls.files['manifest.json'])

    def test_eight_bounded_native_wires_preserve_same_state_and_three_questions(self):
        manifest = self.manifest
        self.assertEqual((len(manifest['requests']), manifest['max_network_attempts']), (8, 24))
        self.assertEqual(manifest['producer_digests'], prep.transport.producer_digests())
        cases = json.loads(prep.source.verify()['packet.json'])['cases']
        for case in cases:
            requests = [r for r in manifest['requests'] if r['case_id'] == case['case_id']]
            self.assertEqual(len(requests), 2)
            self.assertEqual(len({r['native_task_sha256'] for r in requests}), 1)
            self.assertNotEqual(requests[0]['native_task_sha256'], case['task_sha256'])
            states = []
            for item in requests:
                wire = item['wire_json'].encode()
                self.assertEqual(digest(wire), item['wire_sha256'])
                body = json.loads(wire)
                if item['provider'] == 'jev-coreinfra':
                    self.assertEqual(set(body), {'model', 'state', 'questions'})
                    questions, state = body['questions'], body['state']
                else:
                    self.assertEqual(set(body), {'model', 'input', 'questions'})
                    questions = {q['name']: {'type': q['type'], 'instructions': q['instructions'],
                                             'criteria': {c['value']: c['description'] for c in q['choices']}}
                                 for q in body['questions']}
                    state = body['input']
                self.assertEqual(questions, native.QUESTIONS)
                self.assertEqual(json.loads(state), case['state'])
                self.assertEqual(digest(state.encode()), item['wire_state_sha256'])
                self.assertEqual(set(json.loads(state)), {'architecture_profile', 'target', 'bounded_context', 'evaluation_scope'})
                states.append(state)
            self.assertEqual(states[0], states[1])

    def test_offline_verify_and_stage_never_read_credentials_or_send(self):
        prep.verify()
        with tempfile.TemporaryDirectory() as tmp, patch.object(prep.transport.os, 'environ') as env:
            env.get.side_effect = AssertionError('must not read credentials')
            run = Path(tmp) / 'execution'
            result = prep.stage(run)
            self.assertFalse(result['inference'])
            self.assertEqual(result['planned_requests'], 8)
            self.assertEqual([p.name for p in run.iterdir()], ['manifest.json'])
            self.assertEqual(prep.inspect(run)['status'], 'no_response_rows_recorded')
            before = (run / 'manifest.json').read_bytes()
            with self.assertRaises(FileExistsError):
                prep.stage(run)
            self.assertEqual((run / 'manifest.json').read_bytes(), before)

    def test_preparation_and_execution_manifest_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / 'prep'
            prep.write(draft)
            prep.verify(draft)
            with self.assertRaises(FileExistsError):
                prep.write(draft)
            (draft / 'questions.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'preparation bytes'):
                prep.stage(root / 'must-not-exist', draft)
            self.assertFalse((root / 'must-not-exist').exists())
            execution = root / 'execution'
            prep.stage(execution)
            (execution / 'manifest.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'execution manifest'):
                prep.inspect(execution)

    def test_simulated_tls_transport_decodes_eight_projections_without_scoring(self):
        # Integrator labels are test-only mock responses, never provider input/reference scores.
        inputs = prep.source.verify()
        cases = json.loads(inputs['packet.json'])['cases']
        examples = json.loads(inputs['integrator-examples.json'])['annotations']
        labels = {digest(canonical(c['state'])): {k: row[k] for k in native.QUESTIONS}
                  for c, row in zip(cases, examples)}
        def fake_sender(endpoint, wire, key, **kwargs):
            body = json.loads(wire)
            provider = 'jev-coreinfra' if 'state' in body else 'luna-decision-coreinfra'
            selected = labels[digest(body.get('state', body.get('input')).encode())]
            connections = iter([FakeConnection(fail_at='connect', error=ssl.SSLEOFError()),
                                FakeConnection(fail_at='connect', error=ssl.SSLEOFError()),
                                FakeConnection(body=canonical(response(provider, selected)))])
            return post(endpoint, wire, key, **kwargs, connection_factory=lambda _: next(connections), sleep=lambda _: None)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(prep.transport.os.environ, {'COREINFRA_API_KEY': 'test-only-key'}):
            run = Path(tmp) / 'execution'
            prep.stage(run)
            receipt = prep.transport.execute(run, live=True, sender=fake_sender)
            self.assertEqual((receipt['network_attempts'], receipt['potentially_billable_posts']), (24, 8))
            report = prep.inspect(run)
            self.assertEqual(report['observed_response_rows'], 8)
            self.assertEqual(report['requests_without_response_rows'], [])
            self.assertTrue(all(r['prediction']['tuple_consistent'] for r in report['rows']))
            self.assertFalse(report['full_v4_1_annotation'])
            self.assertFalse(report['provider_scoring_enabled'])
            self.assertFalse(report['transport_ledger_verified'])
            self.assertNotIn('test-only-key', (run / 'responses.jsonl').read_text())

    def test_missing_response_rows_do_not_mean_unattempted_or_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / 'execution'
            prep.stage(run)
            report = prep.inspect(run)
            self.assertEqual(len(report['requests_without_response_rows']), 8)
            self.assertFalse(report['execution_inferred_from_missing_rows'])

    def test_report_separates_native_shape_from_inconsistent_projection(self):
        request = self.manifest['requests'][0]
        body = response(request['provider'], {'concern_kind': 'policy', 'evidence_confidence': 'supported',
                                             'recommendation': 'keep_procedural'})
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / 'execution'
            prep.stage(run)
            row = {'request_id': request['request_id'], 'protocol': prep.PROTOCOL,
                   'wire_sha256': request['wire_sha256'], 'status': 'json_received', 'http_status': 200,
                   'response': body}
            (run / 'responses.jsonl').write_bytes(canonical(row) + b'\n')
            observed = prep.inspect(run)['rows'][0]
            self.assertEqual(observed['native_status'], 'valid')
            self.assertEqual(observed['projection_status'], 'inconsistent_native_projection')
            self.assertEqual(observed['prediction']['labels']['recommendation'], 'keep_procedural')

    def test_decoder_inspection_rejects_duplicate_unknown_or_stale_wire_rows(self):
        request = self.manifest['requests'][0]
        item = {'request_id': request['request_id'], 'protocol': prep.PROTOCOL,
                'wire_sha256': request['wire_sha256'], 'status': 'json_received', 'http_status': 200,
                'response': response(request['provider'])}
        for mutation in ('duplicate', 'unknown', 'wire', 'shape'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                run = Path(tmp) / 'execution'
                prep.stage(run)
                row = copy.deepcopy(item)
                if mutation == 'unknown': row['request_id'] = 'unknown'
                if mutation == 'wire': row['wire_sha256'] = '0' * 64
                if mutation == 'shape': row = []
                raw = canonical(row) + b'\n'
                (run / 'responses.jsonl').write_bytes(raw * (2 if mutation == 'duplicate' else 1))
                with self.assertRaises(ValueError): prep.inspect(run)


    def test_report_hash_binds_the_parsed_snapshot_even_if_file_changes_after_read(self):
        request = self.manifest['requests'][0]
        row = {'request_id': request['request_id'], 'protocol': prep.PROTOCOL,
               'wire_sha256': request['wire_sha256'], 'status': 'json_received', 'http_status': 200,
               'response': response(request['provider'])}
        original = canonical(row) + b'\n'
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / 'execution'
            prep.stage(run)
            target = run / 'responses.jsonl'
            target.write_bytes(original)
            real_read = Path.read_bytes
            def changing_read(path):
                data = real_read(path)
                if path == target:
                    target.write_bytes(b'changed after snapshot\n')
                return data
            with patch.object(Path, 'read_bytes', changing_read):
                result = prep.inspect(run)
            self.assertEqual(result['observed_response_rows'], 1)
            self.assertEqual(result['response_file_sha256'], digest(original))


class NativeDecoderTests(unittest.TestCase):
    def parse(self, body, provider='jev-coreinfra'):
        return native.parse_response(canonical(body), provider=provider, model=native.PROVIDERS[provider][0])

    def test_both_native_shapes_keep_ordinal_choice_separate_from_numeric_confidence(self):
        for provider in native.PROVIDERS:
            result = self.parse(response(provider), provider)
            self.assertEqual(result['labels']['evidence_confidence'], 'insufficient')
            self.assertEqual(result['answers']['evidence_confidence']['provider_confidence'], .87)
            self.assertTrue(result['tuple_consistent'])
            self.assertFalse(result['full_v4_1_annotation'])
            self.assertNotIn('rationales', result)
            self.assertNotIn('basis', result)

    def test_contradictory_choices_are_retained_as_observed_not_repaired(self):
        for role, support in (('policy', 'supported'), ('unknown', 'insufficient'), ('mechanics', 'limited')):
            body = response(labels={'concern_kind': role, 'evidence_confidence': support, 'recommendation': 'keep_procedural'})
            result = self.parse(body)
            self.assertEqual(result['labels']['recommendation'], 'keep_procedural')
            self.assertFalse(result['tuple_consistent'])
            self.assertIn('procedural_requires_supported_mechanics', result['tuple_violations'])

    def test_jev_one_percent_mass_warning_preserves_raw_values_but_luna_rejects_it(self):
        for provider in native.PROVIDERS:
            body = response(provider)
            if provider == 'jev-coreinfra':
                body['answers']['concern_kind']['probabilities']['unknown'] = .99
                result = self.parse(body)
                self.assertEqual(result['warnings'][0]['raw_total'], '0.99')
                self.assertEqual(result['answers']['concern_kind']['probabilities']['unknown'], .99)
                body['answers']['concern_kind']['probabilities']['unknown'] = .98
                with self.assertRaises(ChoiceContractError): self.parse(body)
            else:
                body['answers'][0]['probabilities'][0]['probability'] = .01
                with self.assertRaises(ChoiceContractError): self.parse(body, provider)

    def test_invalid_native_models_questions_options_and_numbers_are_rejected(self):
        mutations = [lambda b: b.update(model='wrong'), lambda b: b['answers'].pop('recommendation'),
                     lambda b: b['answers']['concern_kind'].update(type='score'),
                     lambda b: b['answers']['concern_kind'].update(confidence=True),
                     lambda b: b['answers']['concern_kind'].update(choice='missing'),
                     lambda b: b['answers']['concern_kind']['probabilities'].update(extra=0),
                     lambda b: b['answers']['concern_kind']['probabilities'].update(unknown=-1)]
        for mutation in mutations:
            body = response(); mutation(body)
            with self.assertRaises(ChoiceContractError): self.parse(body)
        for mutation in ('duplicate_question', 'duplicate_option'):
            body = response('luna-decision-coreinfra')
            if mutation == 'duplicate_question': body['answers'][1] = body['answers'][0]
            else: body['answers'][0]['probabilities'][1] = body['answers'][0]['probabilities'][0]
            with self.assertRaises(ChoiceContractError): self.parse(body, 'luna-decision-coreinfra')


if __name__ == '__main__':
    unittest.main()
