"""Regression for PR64: shape equality is not declaring-class containment."""
import ast
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import conditional_native_action_v2 as v2
from test_intent_first_native import response


class SourceBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = next(c for c in json.loads(v2.old.previous.source.verify()['packet.json'])['cases']
                        if c['case_id'] == v2.old.BDD)
        cls.source_raw, cls.sources = v2.sources()

    def test_direct_class_containment_and_pinned_source_identity(self):
        witness = v2.bind_witness(self.case, self.sources)
        binding = next(b for b in witness['source_bindings'] if b['fragment_id'] == 'fragment-03')
        self.assertEqual(binding['defining_symbol'], 'BDDPolicy._evaluate')
        self.assertEqual(binding['path'], 'tools/native_bdd/policy.py')
        self.assertEqual(binding['span'], [31, 4, 32, 43])
        self.assertEqual(witness['source_snapshot_sha256'], v2.digest(self.source_raw))

    def test_identical_method_in_unrelated_class_is_rejected(self):
        # Preserve the free snippet unchanged: old shape-only witness still accepts it.
        self.assertEqual(v2.old.witness(self.case)['verdict_path'],
                         'BDDPolicy._evaluate -> self.findings(candidate)')
        changed = dict(self.sources)
        module = ast.parse(changed['tools/native_bdd/policy.py'])
        policy = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == 'BDDPolicy')
        method = next(n for n in policy.body if isinstance(n, ast.FunctionDef) and n.name == '_evaluate')
        policy.body.remove(method)
        module.body.append(ast.ClassDef(name='Unrelated', bases=[], keywords=[], body=[method], decorator_list=[]))
        changed['tools/native_bdd/policy.py'] = ast.unparse(module)
        with self.assertRaisesRegex(ValueError, 'unique direct declaration: _evaluate'):
            v2.bind_witness(self.case, changed)

    def test_snapshot_changes_and_wrong_method_body_are_rejected(self):
        with patch.object(Path, 'read_bytes', return_value=self.source_raw + b'\n'):
            with self.assertRaisesRegex(ValueError, 'snapshot differs'):
                v2.sources()
        changed = dict(self.sources)
        changed['tools/native_bdd/policy.py'] = changed['tools/native_bdd/policy.py'].replace(
            'return not self.findings(candidate)', 'return True')
        with self.assertRaisesRegex(ValueError, 'fragment-03 is not BDDPolicy._evaluate'):
            v2.bind_witness(self.case, changed)

    def test_only_two_witness_wires_change_and_old_package_still_replays(self):
        before = json.loads(v2.old.verify()['manifest.json'])['requests']
        after = json.loads(v2.build()['manifest.json'])['requests']
        self.assertEqual(len(after), 18)
        changed = []
        for a, b in zip(before, after):
            self.assertNotEqual(a['request_id'], b['request_id'])
            self.assertNotEqual(a['diagnostic_task_sha256'], b['diagnostic_task_sha256'])
            if a['wire_json'] != b['wire_json']:
                changed.append(b['arm'])
            else:
                self.assertNotEqual(b['arm'], 'ownership_witness')
        self.assertEqual(changed, ['ownership_witness', 'ownership_witness'])

    def test_offline_stage_and_inspect_both_providers_without_credentials(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(v2.old.previous.transport.os, 'environ') as env:
            env.get.side_effect = AssertionError('no credentials offline')
            prep = Path(tmp) / 'prep'
            v2.write(prep)
            run = Path(tmp) / 'run'
            self.assertEqual(v2.stage(run, prep)['max_network_attempts'], 54)
            self.assertEqual(len(v2.inspect(run, prep)['requests_without_response_rows']), 18)
            with self.assertRaises(FileExistsError):
                v2.stage(run, prep)
            requests = json.loads((prep / 'manifest.json').read_bytes())['requests']
            rows = []
            for request in (r for r in requests if r['arm'] == 'ownership_witness'):
                labels = dict(concern_kind='policy', evidence_confidence='supported', recommendation='formalize')
                rows.append(dict(request_id=request['request_id'], protocol=v2.old.previous.PROTOCOL,
                                 wire_sha256=request['wire_sha256'], status='json_received', http_status=200,
                                 response=response(request['provider'], labels)))
            (run / 'responses.jsonl').write_bytes(b''.join(v2.canonical(r) + b'\n' for r in rows))
            report = v2.inspect(run, prep)
            self.assertEqual(len(report['rows']), 2)
            self.assertTrue(all(r['premise_echo_matches'] and r['native_status'] == 'valid'
                                and r['bdd_reuse_diagnostic'] == 'existing_specification_not_reused'
                                for r in report['rows']))
            self.assertFalse(report['transport_ledger_verified'])
            self.assertFalse(report['provider_scoring_enabled'])
            rows[0]['wire_sha256'] = '0' * 64
            (run / 'responses.jsonl').write_bytes(v2.canonical(rows[0]) + b'\n')
            with self.assertRaisesRegex(ValueError, 'wire binding'):
                v2.inspect(run, prep)


if __name__ == '__main__':
    unittest.main()
