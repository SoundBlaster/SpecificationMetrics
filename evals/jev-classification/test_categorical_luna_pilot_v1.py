import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx2

import categorical_luna_pilot_v1 as pilot
from coreinfra_retry_run import decode, sha
from retrieval_index_v1.source import encoded


def unknown_answers():
    return dict(concern_kind='unknown', evidence_confidence='insufficient',
                ownership='unknown', tool_responsibility='unknown')


def factory(body=None, calls=None):
    body = pilot.envelope(unknown_answers()) if body is None else body
    calls = [] if calls is None else calls

    def make(item):
        def handle(request):
            calls.append(item['request_id'])
            return httpx2.Response(200, content=body,
                headers={'content-type': 'application/json', 'x-request-id': 'synthetic-request'})
        return httpx2.MockTransport(handle)
    return make


class CategoricalPilotTests(unittest.TestCase):
    def test_recorded_live_pilot_reconstructs_labels_ledger_and_receipt_offline(self):
        result = pilot.score(pilot.PREPARATION, pilot.RUN)
        self.assertEqual(result, decode((pilot.RUN / 'comparison.json').read_bytes()))
        self.assertEqual(result['agreement_status'], 'complete_label_comparison')
        ordinary = result['ordinary_luna']
        self.assertEqual((ordinary['all_axis_matches'], ordinary['primary_axis_matches'], ordinary['consistency_review']),
                         (32, 16, 0))
        self.assertEqual((ordinary['valid_label_responses'], ordinary['coherent'], ordinary['unknown_role']), (8, 8, 0))
        self.assertEqual(result['new_sol_calls'], 0)
        self.assertFalse(result['automatic_fact_acceptance'])
        receipt = decode((pilot.RUN / 'result-receipt.json').read_bytes())
        self.assertEqual(receipt['producer_sha256'], pilot.producers())
        self.assertEqual(receipt['file_sha256'], {str(p.relative_to(pilot.RUN)): sha(p.read_bytes())
            for p in pilot.RUN.rglob('*') if p.is_file() and p.name != 'result-receipt.json'})
        self.assertEqual(receipt['preparation_receipt_sha256'], result['preparation_receipt_sha256'])
        self.assertEqual(receipt['status'], 'complete')
        self.assertIsNone(receipt['semantic_accuracy'])
        self.assertFalse(receipt['automatic_fact_acceptance'])
        for line in (pilot.RUN / 'responses.jsonl').read_bytes().splitlines():
            metadata = decode(line)['result']
            self.assertNotIn('probabilities', metadata)
            self.assertNotIn('confidence', metadata)

    def test_audit_reads_forwarded_stream_and_dispatches_identical_bytes_once(self):
        raw, observed, events = b'{"fixture":true}', [], []
        item = {'request_json': raw.decode()}

        def handle(request):
            observed.append(request.content)
            return httpx2.Response(200)

        transport = pilot.DispatchTransport(httpx2.MockTransport(handle), item, events.append)
        request = httpx2.Request('POST', pilot.ENDPOINT, content=iter([raw[:5], raw[5:]]))
        with self.assertRaises(httpx2.RequestNotRead):
            request.content
        transport.handle_request(request)
        self.assertEqual(observed, [raw])
        self.assertEqual(len(events), 1)
        with self.assertRaises(ValueError):
            transport.handle_request(request)
        self.assertEqual(observed, [raw])
        transport.close()

    def test_semantic_parity_and_real_sdk_rendering_without_credentials_or_network(self):
        with patch.dict('os.environ', {}, clear=True):
            manifest = pilot.expected()
        original = pilot.parity.verify(pilot.parity.PREPARATION)
        self.assertEqual((manifest['planned_requests'], manifest['max_http_dispatches'], manifest['new_sol_calls']), (8, 8, 0))
        for item in manifest['requests']:
            native = next(r for r in original['requests'] if r['request_id'] == item['source_request_id'])
            wire = decode(native['wire_json'])
            self.assertEqual(item['task']['state'], decode(wire['state']))
            self.assertEqual(item['task']['questions'], {k: {a: q[a] for a in ('instructions', 'criteria')}
                for k, q in wire['questions'].items()})
            payload = decode(item['request_json'])
            self.assertEqual(decode(payload['input']), {'state': item['task']['state']})
            self.assertEqual(decode(payload['instructions'].split('\n', 1)[1]), item['task']['questions'])
            self.assertTrue(payload['text']['format']['strict'])
            self.assertEqual(payload['reasoning'], {'effort': 'low'})
            self.assertFalse(payload['store'])
            self.assertEqual(payload['truncation'], 'disabled')

    def test_full_synthetic_run_replays_labels_and_blocks_wire_result_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            preparation, run = (Path(directory) / n for n in ('preparation', 'run'))
            pilot.freeze(preparation)
            pilot.stage(preparation, run)
            calls = []
            self.assertFalse(pilot.execute(preparation, run, transport_factory=factory(calls=calls))['inference'])
            self.assertEqual(calls, [])
            with patch.dict('os.environ', COREINFRA_API_KEY='synthetic-test-key'):
                receipt = pilot.execute(preparation, run, live=True, transport_factory=factory(calls=calls))
                with self.assertRaises(ValueError):
                    pilot.execute(preparation, run, live=True, transport_factory=factory(calls=calls))
            self.assertEqual((len(calls), receipt['http_dispatches'], receipt['successful_tasks']), (8, 8, 8))
            result = pilot.score(preparation, run)
            self.assertEqual(result['agreement_status'], 'complete_label_comparison')
            self.assertEqual(result['ordinary_luna']['valid_label_responses'], 8)
            self.assertEqual(result['ordinary_luna']['coherent'], 8)
            self.assertFalse(result['automatic_fact_acceptance'])
            self.assertIsNone(result['semantic_accuracy'])
            path = run / 'responses.jsonl'
            rows = [decode(line) for line in path.read_bytes().splitlines()]
            rows[0]['result']['answers']['concern_kind'] = 'policy'
            path.write_text(''.join(encoded(r) + '\n' for r in rows))
            receipt['file_sha256']['responses.jsonl'] = sha(path.read_bytes())
            (run / 'receipt.json').write_text(encoded(receipt))
            with self.assertRaisesRegex(ValueError, 'result replay differs'):
                pilot.inspect(preparation, run)

    def test_incomplete_refusal_and_model_mismatch_stop_without_abstention_or_retry(self):
        base = decode(pilot.envelope(unknown_answers()))
        incomplete = dict(base, status='incomplete', incomplete_details={'reason': 'max_output_tokens'})
        refused = copy.deepcopy(base)
        refused['output'][0]['content'] = [{'type': 'refusal', 'refusal': 'Synthetic refusal'}]
        wrong_model = dict(base, model='another-model')
        with tempfile.TemporaryDirectory() as directory:
            preparation = Path(directory) / 'preparation'
            pilot.freeze(preparation)
            for name, body, status in (
                    ('incomplete', incomplete, 'ResponsesIncompleteError'),
                    ('refused', refused, 'ResponsesRefusalError'),
                    ('model', wrong_model, 'response_identity_error')):
                with self.subTest(name=name):
                    run = Path(directory) / name
                    pilot.stage(preparation, run)
                    calls = []
                    with patch.dict('os.environ', COREINFRA_API_KEY='synthetic-test-key'):
                        receipt = pilot.execute(preparation, run, live=True, transport_factory=factory(encoded(body).encode(), calls))
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(receipt['stop_reason'], status)
                    result = pilot.score(preparation, run)
                    self.assertEqual(result['agreement_status'], 'not_evaluable_incomplete_cohort')
                    self.assertEqual(result['transport']['errors'][0]['status'], status)
                    self.assertEqual(result['ordinary_luna']['valid_label_responses'], 0)
                    self.assertEqual(result['ordinary_luna']['planned_axis_slots'], 32)
                    self.assertEqual(result['ordinary_luna']['unknown_role'], 0)

    def test_rebound_preparation_cannot_change_state_effort_or_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            preparation = Path(directory) / 'preparation'
            pilot.freeze(preparation)
            path = preparation / 'manifest.json'
            raw = path.read_bytes()
            for kind in ('state', 'effort', 'budget'):
                with self.subTest(kind=kind):
                    manifest = decode(raw)
                    if kind == 'state':
                        manifest['requests'][0]['task']['state']['extra_author_hint'] = 'Select policy'
                    elif kind == 'effort':
                        manifest['settings']['reasoning_effort'] = 'high'
                    else:
                        manifest['max_http_dispatches'] = 9
                    path.write_text(encoded(manifest) + '\n')
                    receipt_path = preparation / 'preparation-receipt.json'
                    receipt = decode(receipt_path.read_bytes())
                    receipt['manifest_sha256'] = sha(path.read_bytes())
                    receipt_path.write_text(encoded(receipt))
                    with self.assertRaises(ValueError):
                        pilot.verify(preparation)

    def test_label_consistency_uses_same_specifications_without_probabilities(self):
        labels = unknown_answers()
        self.assertEqual(pilot.consistency(labels)['violations'], [])
        labels['concern_kind'] = 'policy'
        self.assertEqual(pilot.consistency(labels)['violations'], ['unknown_requires_insufficient_and_vice_versa'])
        labels['evidence_confidence'] = 'supported'
        self.assertEqual(pilot.consistency(labels)['violations'], [])
        self.assertNotIn('probabilities', pilot.consistency(labels))


if __name__ == '__main__':
    unittest.main()
