"""Check that the curated workflow excerpt witnesses the claimed consumers."""
import json
from pathlib import Path
import shlex
import unittest

from question_grouping import digest

RUN = Path(__file__).parent / 'runs/2026-10-13-manifest-path-contract-audit'


def validate_workflow_witness(text):
    calls = []
    for line in text.replace('\\\n', ' ').splitlines():
        tokens = shlex.split(line)
        if tokens[:3] == ['python', 'tools/static_artifact_incremental_stage.py', 'stage']:
            if len(tokens[3:]) % 2:
                raise ValueError('Malformed staging call')
            calls.append(dict(zip(tokens[3::2], tokens[4::2])))
    expected = []
    for prefix in ('', 'workspaces/team-decision-log', 'workspaces/hosted-operation-canary'):
        suffix = '/' + prefix if prefix else ''
        expected.append({'--bundle-dir': 'dist/specgraph-public' + suffix,
                         '--remote-manifest-url': '$STATIC_ARTIFACT_PUBLIC_BASE_URL' + suffix + '/artifact_manifest.json',
                         '--staging-dir': '$INCREMENTAL_STAGE_DIR',
                         **({'--staging-prefix': prefix} if prefix else {})})
    actual = [{k: v for k, v in call.items() if k != '--output'} for call in calls]
    if actual != expected:
        raise ValueError('Workflow witness must preserve three scoped staging calls and both prefixes')


class ManifestPathContractAuditTests(unittest.TestCase):
    def setUp(self):
        self.audit = json.loads((RUN / 'source-contract-audit.json').read_text())
        self.fact = self.audit['source_facts']['workflow-independent-bases']

    def test_saved_workflow_witness(self):
        validate_workflow_witness(self.fact['text'])

    def test_workflow_byte_and_source_identity(self):
        self.assertEqual(digest(self.fact['text'].encode()), self.fact['excerpt_sha256'])
        self.assertEqual(self.fact['file_sha256'], self.audit['file_sha256'][self.fact['path']])
        self.assertEqual(self.fact['lines'], [233, 255])
        self.assertEqual(self.fact['source_url'],
                         'https://github.com/0al-spec/SpecGraph/blob/' + self.audit['source_revision']
                         + '/' + self.fact['path'] + '#L233-L255')
        repair = json.loads((RUN / 'review-repair-receipt.json').read_text())
        self.assertEqual(repair['corrected_workflow_fact'], self.fact)
        self.assertEqual(repair['corrected_audit_sha256'], digest((RUN / 'source-contract-audit.json').read_bytes()))

    def test_original_setup_only_excerpt_is_not_a_consumer_witness(self):
        repair = json.loads((RUN / 'review-repair-receipt.json').read_text())
        original = repair['original_workflow_fact']
        self.assertEqual(digest(original['text'].encode()), original['excerpt_sha256'])
        with self.assertRaisesRegex(ValueError, 'three scoped staging calls'):
            validate_workflow_witness(original['text'])

    def test_rejects_lost_workspace_prefix_or_misrouted_base(self):
        text = self.fact['text']
        for wrong in (text.replace('--staging-prefix workspaces/team-decision-log', '--staging-prefix workspaces/other'),
                      text.replace('$STATIC_ARTIFACT_PUBLIC_BASE_URL/workspaces/hosted-operation-canary/',
                                   '$STATIC_ARTIFACT_PUBLIC_BASE_URL/')):
            with self.assertRaisesRegex(ValueError, 'three scoped staging calls'):
                validate_workflow_witness(wrong)


if __name__ == '__main__':
    unittest.main()
