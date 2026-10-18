"""SDK 0.9 compatibility with captured 0.8 requests; no new model evidence."""
import base64
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import httpx2
import mellea_jev
from mellea_jev import ResponsesIncompleteError, ResponsesRefusalError

import categorical_luna_pilot_v1 as historical


ROOT = Path(__file__).resolve().parent
COMMIT = 'e94d6ba1808b95208ef8ac05da7b256f3988532f'
RECEIPT_SHA = 'ee23a4e6c6625adbb5b561028a1e5eb688650ce12a0482797e8eda2f32282b49'


class Jev4MelleaCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Anchor the fixture independently of its self-reported file hashes.
        raw = (historical.RUN / 'result-receipt.json').read_bytes()
        if hashlib.sha256(raw).hexdigest() != RECEIPT_SHA:
            raise AssertionError('historical result receipt changed')
        receipt = json.loads(raw)
        for name in ('manifest.json', 'responses.jsonl'):
            if hashlib.sha256((historical.RUN / name).read_bytes()).hexdigest() != receipt['file_sha256'][name]:
                raise AssertionError('historical fixture changed: ' + name)
        cls.manifest = json.loads((historical.RUN / 'manifest.json').read_bytes())
        cls.responses = [json.loads(line) for line in (historical.RUN / 'responses.jsonl').read_bytes().splitlines()]

    def test_installed_release_and_git_commit_match_current_lock(self):
        distribution = importlib.metadata.distribution('mellea-jev-adapter')
        self.assertEqual(distribution.version, '0.9.0')
        self.assertEqual(mellea_jev.__version__, '0.9.0')
        origin = json.loads(distribution.read_text('direct_url.json'))
        self.assertEqual(origin['url'], 'https://github.com/SoundBlaster/Jev4Mellea.git')
        self.assertEqual(origin['vcs_info']['commit_id'], COMMIT)
        for name in ('requirements-evaluation.txt', 'requirements-evaluation.lock'):
            self.assertIn('@' + COMMIT, (ROOT / name).read_text())

    def test_all_eight_tasks_render_identical_request_bytes(self):
        self.assertEqual(len(self.manifest['requests']), 8)
        with patch.dict('os.environ', {}, clear=True):
            for item in self.manifest['requests']:
                with self.subTest(request_id=item['request_id']):
                    task = historical.task_from(item['task'])
                    self.assertEqual(task.to_dict(), item['task'])
                    rendered = historical.render(task)
                    self.assertEqual(rendered, item['request_json'])
                    self.assertEqual(hashlib.sha256(rendered.encode()).hexdigest(), item['request_sha256'])

    def test_all_eight_captured_responses_preserve_complete_result_records(self):
        self.assertEqual(len(self.responses), 8)
        self.assertEqual([r['request_id'] for r in self.responses],
                         [r['request_id'] for r in self.manifest['requests']])
        with patch.dict('os.environ', {}, clear=True):
            for item, row in zip(self.manifest['requests'], self.responses):
                with self.subTest(request_id=item['request_id']):
                    body = base64.b64decode(row['sdk_response_base64'], validate=True)
                    self.assertEqual(hashlib.sha256(body).hexdigest(), row['sdk_response_sha256'])
                    self.assertEqual(historical.replay(item, body, row['result']['request_id']), row['result'])

    def test_incomplete_and_refused_answers_still_raise_without_retry(self):
        answers = {name: 'insufficient' if name == 'evidence_confidence' else 'unknown'
                   for name in self.manifest['requests'][0]['task']['questions']}
        base = json.loads(historical.envelope(answers))
        incomplete = dict(base, status='incomplete', incomplete_details={'reason': 'max_output_tokens'})
        refused = copy.deepcopy(base)
        refused['output'][0]['content'] = [{'type': 'refusal', 'refusal': 'Synthetic refusal'}]
        for body, error in ((incomplete, ResponsesIncompleteError), (refused, ResponsesRefusalError)):
            with self.subTest(error=error.__name__):
                calls = []

                def handle(request):
                    calls.append(request.content)
                    return httpx2.Response(200, json=body)

                with historical.provider(key=historical.OFFLINE_KEY, transport=httpx2.MockTransport(handle)) as client:
                    with self.assertRaises(error):
                        client.classify(historical.task_from(self.manifest['requests'][0]['task']))
                self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
