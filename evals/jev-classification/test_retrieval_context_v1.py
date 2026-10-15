import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prepare_retrieval_context_v1 import QUESTIONS, prepare, verify_bundle, write_bundle
from retrieval_index_v1.source import digest
from test_retrieval_index_v1 import CODE, PROFILE


class Encoder:
    def __init__(self):
        self.profile = copy.deepcopy(PROFILE)
        self.document_calls = []
        self.query_calls = []

    def __call__(self, texts):
        self.document_calls.extend(texts)
        return [[1.0, 0.0] for _ in texts]

    def query(self, text):
        self.query_calls.append(text)
        return [1.0, 0.0]


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Context test')
        self.git('config', 'user.email', 'context@example.invalid')
        (self.repo / 'tools').mkdir()
        self.path = self.repo / 'tools/policy.py'
        self.path.write_text(CODE)
        self.commit()
        self.encoder = Encoder()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.PIPE)

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-qm', 'fixture', '--allow-empty')

    def prepare(self, **kwargs):
        return prepare(self.repo, 'fixture', 'HEAD', ('tools/*.py',), (), self.root / 'index.sqlite',
                       self.encoder, 'tools/policy.py::allowed', 'Find the rule for positive values', **kwargs)

    def test_refresh_then_context_has_exact_sources_and_equal_provider_state(self):
        packet = self.prepare()
        self.assertEqual(packet['index_refresh']['encode_inputs'], 3)
        state = packet['state']
        self.assertEqual([d['id'] for d in state['retrieved_context']],
                         ['tools/policy.py::Rule', 'tools/policy.py::unrelated'])
        self.assertEqual(state['accepted_facts']['ownership']['value'], 'unknown')
        self.assertEqual(state['accepted_facts']['intent_lookup']['value'], 'not_done')
        self.assertIn('goal', state['architecture_profile'])
        jev, luna = [json.loads(r['wire_json']) for r in packet['requests']]
        self.assertEqual(jev['state'], luna['input'])
        self.assertEqual(digest(jev['state']), packet['state_sha256'])
        self.assertEqual(set(jev['questions']), {q['name'] for q in luna['questions']})
        self.assertEqual(set(jev['questions']), set(QUESTIONS))
        self.assertNotIn('recommendation', jev['questions'])
        self.assertNotIn('absent_in_scope', jev['questions']['ownership']['criteria'])
        self.assertFalse(packet['automatic_fact_acceptance'])
        self.assertFalse(packet['inference_authorized'])

    def test_noop_refresh_does_not_change_model_context(self):
        first = self.prepare()
        second = self.prepare()
        self.assertEqual(second['index_refresh']['encode_inputs'], 0)
        self.assertEqual(first['state_sha256'], second['state_sha256'])
        self.assertEqual(first['requests'], second['requests'])
        self.assertEqual(len(self.encoder.document_calls), 3)
        self.assertEqual(len(self.encoder.query_calls), 2)

    def test_changed_helper_refreshes_wrapper_context_before_request(self):
        first = self.prepare()
        self.path.write_text(CODE.replace('value > 0', 'value > 20'))
        self.commit()
        second = self.prepare()
        self.assertEqual(second['index_refresh']['encode_inputs'], 2)
        wrapper = next(d for d in second['state']['retrieved_context'] if d['id'].endswith('::Rule'))
        self.assertIn('value > 20', wrapper['helpers'][0]['code'])
        self.assertNotEqual(first['state_sha256'], second['state_sha256'])
        self.assertNotEqual(first['fact_plan']['facts_sha256'], second['fact_plan']['facts_sha256'])

    def test_removed_candidate_is_absent_and_empty_hits_do_not_become_absence(self):
        self.prepare()
        self.path.write_text(CODE.split('\nRule =')[0])
        self.commit()
        packet = self.prepare()
        self.assertEqual(packet['state']['retrieved_context'], [])
        self.assertEqual(packet['index_refresh']['removed'], 2)
        self.assertFalse(packet['retrieval']['query_encoded'])
        self.assertEqual(packet['state']['accepted_facts']['ownership']['value'], 'unknown')

    def test_byte_budget_omits_whole_hits_without_truncating_source(self):
        packet = self.prepare(context_bytes=0)
        self.assertEqual(packet['retrieval']['returned'], 0)
        self.assertEqual(len(packet['retrieval']['omitted_for_budget']), 2)
        self.assertIn('return ready', packet['state']['target']['source']['code'])
        with self.assertRaisesRegex(ValueError, 'before retrieval'):
            self.prepare(state_bytes=1)

    def test_failed_refresh_or_stale_read_never_returns_context(self):
        self.prepare()
        self.path.write_text(CODE.replace('value > 0', 'value > 20'))
        self.commit()
        with patch('prepare_retrieval_context_v1.update', side_effect=RuntimeError('encoder failed')):
            with self.assertRaisesRegex(RuntimeError, 'encoder failed'):
                self.prepare()
        with patch('prepare_retrieval_context_v1.update', return_value={}):
            with self.assertRaisesRegex(ValueError, 'stale'):
                self.prepare()

    def test_moving_ref_is_rejected_after_encoding(self):
        original = self.encoder.query

        def move(text):
            self.commit()
            return original(text)

        self.encoder.query = move
        with self.assertRaisesRegex(ValueError, 'ref moved'):
            self.prepare()

    def test_invalid_query_vector_and_target_are_rejected(self):
        self.encoder.query = lambda text: [0.0, 0.0]
        with self.assertRaisesRegex(ValueError, 'normalized'):
            self.prepare()
        self.path.write_text('pass\n')
        self.commit()
        with self.assertRaisesRegex(ValueError, 'uniquely indexed'):
            self.prepare()

    def test_bundle_is_bound_and_never_overwrites(self):
        packet = self.prepare()
        output = self.root / 'bundle'
        write_bundle(output, packet)
        receipt = json.loads((output / 'preparation-receipt.json').read_text())
        self.assertEqual(receipt['status'], 'complete_preparation_not_live_authorized')
        for name, sha in receipt['file_sha256'].items():
            self.assertEqual(digest((output / name).read_text()), sha)
        with self.assertRaises(FileExistsError):
            write_bundle(output, packet)
        self.assertEqual(verify_bundle(output), packet)
        (output / 'jev-coreinfra.json').write_text('{}\n')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            verify_bundle(output)
        (output / 'preparation-receipt.json').unlink()
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            verify_bundle(output)


if __name__ == '__main__':
    unittest.main()
