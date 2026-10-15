"""Controlled intervention, source witness and evidence-boundary regressions; offline."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import conditional_native_action_v1 as diagnostic
from question_grouping import canonical, digest
from test_intent_first_native import response


class ConditionalActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = diagnostic.build()
        cls.manifest = json.loads(cls.files['manifest.json'])
        cls.cases = json.loads(diagnostic.previous.source.verify()['packet.json'])['cases']

    def test_exact_budget_and_native_shape_across_providers(self):
        m = self.manifest
        self.assertEqual((m['planned_requests'], len(m['requests']), m['max_network_attempts']), (18, 18, 54))
        self.assertEqual(len({r['request_id'] for r in m['requests']}), 18)
        self.assertEqual({p: sum(r['provider'] == p for r in m['requests']) for p in diagnostic.native.PROVIDERS},
                         {p: 9 for p in diagnostic.native.PROVIDERS})
        for request in m['requests']:
            body = json.loads(request['wire_json'])
            self.assertEqual(digest(request['wire_json'].encode()), request['wire_sha256'])
            if request['provider'] == 'jev-coreinfra':
                questions = body['questions']
            else:
                questions = {q['name']: dict(type=q['type'], instructions=q['instructions'],
                                            criteria={c['value']: c['description'] for c in q['choices']})
                             for q in body['questions']}
            self.assertEqual(questions, diagnostic.questions(request['arm']))
            self.assertEqual(set(questions), set(diagnostic.native.QUESTIONS))

    def test_baseline_is_fresh_identity_but_exact_old_wire(self):
        previous = json.loads(diagnostic.previous.verify()['manifest.json'])['requests']
        lookup = {(r['case_id'], r['provider']): r for r in previous}
        baselines = [r for r in self.manifest['requests'] if r['arm'] == 'baseline']
        self.assertEqual(len(baselines), 8)
        for request in baselines:
            prior = lookup[request['case_id'], request['provider']]
            self.assertEqual(request['wire_json'], prior['wire_json'])
            self.assertNotEqual(request['request_id'], prior['request_id'])

    def test_intervention_changes_only_bound_premises_and_existing_bdd_witness(self):
        self.assertEqual(diagnostic.questions('conditioned'), diagnostic.questions('ownership_witness'))
        cases = {c['case_id']: c for c in self.cases}
        premises = json.loads(self.files['premises.json'])['roles']
        states = {}
        for request in self.manifest['requests']:
            body = json.loads(request['wire_json'])
            state = json.loads(body.get('state', body.get('input')))
            states[request['case_id'], request['arm'], request['provider']] = copy.deepcopy(state)
            binding = state.pop('diagnostic_bindings', None)
            self.assertEqual(state, cases[request['case_id']]['state'])
            if request['arm'] == 'baseline':
                self.assertIsNone(binding)
                continue
            self.assertEqual({k: binding[k] for k in ('concern_kind', 'evidence_confidence')},
                             premises[request['case_id']])
            self.assertNotIn('recommendation', binding)
            self.assertNotIn('formalize', canonical(binding).decode())
            self.assertEqual('ownership_witness' in binding, request['arm'] == 'ownership_witness')
            if request['arm'] == 'ownership_witness':
                self.assertEqual(request['case_id'], diagnostic.BDD)
        for case in self.cases:
            for arm in diagnostic.ARMS if case['case_id'] == diagnostic.BDD else diagnostic.ARMS[:2]:
                self.assertEqual(states[case['case_id'], arm, 'jev-coreinfra'],
                                 states[case['case_id'], arm, 'luna-decision-coreinfra'])

    def test_witness_rejects_broken_inheritance_target_verdict_and_receiver(self):
        case = next(c for c in self.cases if c['case_id'] == diagnostic.BDD)
        for fragment, old, new in (
            ('fragment-01', 'BDDScenarioValuesSpec(BDDPolicy)', 'BDDScenarioValuesSpec(object)'),
            ('fragment-01', 'if not step.valid', 'if step.valid'),
            ('fragment-02', 'Specification[BDDContext]', 'object'),
            ('fragment-03', 'return not self.findings(candidate)', 'return True'),
            ('fragment-05', 'for policy in POLICIES:', 'for policy in OTHER_POLICIES:'),
        ):
            changed = copy.deepcopy(case)
            source = next(f for f in changed['state']['bounded_context']['fragments'] if f['fragment_id'] == fragment)
            source['code'] = source['code'].replace(old, new)
            with self.subTest(fragment=fragment), self.assertRaises(ValueError):
                diagnostic.witness(changed)

    def test_staging_never_reads_credentials_or_sends_and_refuses_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(diagnostic.previous.transport.os, 'environ') as env:
            env.get.side_effect = AssertionError('offline must not read credentials')
            with patch.object(diagnostic.previous.transport, 'post', side_effect=AssertionError('no network')):
                preparation = Path(tmp) / 'prepared'
                diagnostic.write(preparation)
                diagnostic.verify(preparation)
                run = Path(tmp) / 'execution'
                result = diagnostic.stage(run, preparation)
                self.assertEqual((result['planned_requests'], result['max_network_attempts'], result['inference']),
                                 (18, 54, False))
                with self.assertRaises(FileExistsError):
                    diagnostic.stage(run, preparation)
                with self.assertRaises(FileExistsError):
                    diagnostic.write(preparation)
                report = diagnostic.inspect(run, preparation)
                self.assertEqual(len(report['requests_without_response_rows']), 18)
                self.assertFalse(report['execution_inferred_from_missing_rows'])
                self.assertFalse(report['transport_ledger_verified'])
                (preparation / 'ownership-witness.json').write_text('{}')
                with self.assertRaises(ValueError):
                    diagnostic.stage(Path(tmp) / 'not-created', preparation)
                self.assertFalse((Path(tmp) / 'not-created').exists())

    def observed(self, request, labels, mutate=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preparation = root / 'preparation'
            diagnostic.write(preparation)
            run = root / 'execution'
            diagnostic.stage(run, preparation)
            row = dict(request_id=request['request_id'], protocol=diagnostic.previous.PROTOCOL,
                       wire_sha256=request['wire_sha256'], status='json_received', http_status=200,
                       response=response(request['provider'], labels))
            if mutate:
                mutate(row)
            (run / 'responses.jsonl').write_bytes(canonical(row) + b'\n')
            return diagnostic.inspect(run, preparation)['rows'][0]

    def test_wrong_premise_echo_is_separate_from_tuple_and_conditional_action(self):
        request = next(r for r in self.manifest['requests'] if r['case_id'] == 'target-02-cell01'
                       and r['arm'] == 'conditioned')
        labels = dict(concern_kind='mechanics', evidence_confidence='supported', recommendation='keep_procedural')
        row = self.observed(request, labels)
        self.assertEqual(row['projection_status'], 'consistent_native_projection')
        self.assertFalse(row['premise_echo_matches'])
        self.assertEqual(row['action_violations_against_development_premises'],
                         ['procedural_requires_supported_mechanics'])
        self.assertEqual(row['prediction']['labels'], labels)

    def test_consistent_bdd_formalization_is_retained_and_flagged_as_missed_reuse(self):
        for arm in diagnostic.ARMS:
            request = next(r for r in self.manifest['requests'] if r['case_id'] == diagnostic.BDD and r['arm'] == arm)
            labels = dict(concern_kind='policy', evidence_confidence='supported', recommendation='formalize')
            row = self.observed(request, labels)
            self.assertEqual(row['projection_status'], 'consistent_native_projection')
            self.assertEqual(row['bdd_reuse_diagnostic'], 'existing_specification_not_reused')
            self.assertEqual(row['prediction']['labels'], labels)
        row = self.observed(request, dict(labels, recommendation='reuse_specification'))
        self.assertEqual(row['bdd_reuse_diagnostic'], 'reuse_selected')

    def test_native_invalid_and_stale_rows_do_not_become_semantic_failures(self):
        request = self.manifest['requests'][0]
        labels = dict(concern_kind='policy', evidence_confidence='supported', recommendation='formalize')
        row = self.observed(request, labels, lambda r: r['response'].update(model='wrong'))
        self.assertEqual(row['native_status'], 'invalid')
        self.assertIsNone(row['action_violations_against_development_premises'])
        with self.assertRaises(ValueError):
            self.observed(request, labels, lambda r: r.update(wire_sha256='0' * 64))

    def test_response_hash_binds_one_parsed_snapshot(self):
        request = self.manifest['requests'][0]
        labels = dict(concern_kind='policy', evidence_confidence='supported', recommendation='formalize')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preparation = root / 'preparation'
            diagnostic.write(preparation)
            run = root / 'execution'
            diagnostic.stage(run, preparation)
            row = dict(request_id=request['request_id'], protocol=diagnostic.previous.PROTOCOL,
                       wire_sha256=request['wire_sha256'], status='json_received', http_status=200,
                       response=response(request['provider'], labels))
            raw = canonical(row) + b'\n'
            target = run / 'responses.jsonl'
            target.write_bytes(raw)
            read = Path.read_bytes
            def changing_read(path):
                value = read(path)
                if path == target:
                    target.write_bytes(b'changed after parsing snapshot\n')
                return value
            with patch.object(Path, 'read_bytes', changing_read):
                report = diagnostic.inspect(run, preparation)
            self.assertEqual(report['response_file_sha256'], digest(raw))
            self.assertEqual(len(report['rows']), 1)


if __name__ == '__main__':
    unittest.main()
