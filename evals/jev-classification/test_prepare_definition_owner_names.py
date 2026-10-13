from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from prepare_context_reference_v2 import task_digest
from prepare_definition_owner_names import (
    AUDIT, CONDITIONS, PROMPT, RUN, build, rename_identifiers, verify,
)
from question_grouping import canonical, digest


class DefinitionOwnerNamesPreparation(unittest.TestCase):
    def test_frozen_replay_binds_producer_inputs_and_artifacts(self):
        outputs = verify()
        receipt = outputs['preparation-receipt.json']
        root = RUN.parents[1]
        self.assertEqual(receipt['producer_sha256'], digest((root / 'prepare_definition_owner_names.py').read_bytes()))
        for name, sha in receipt['input_file_sha256'].items():
            self.assertEqual(sha, digest((root / name).read_bytes()))
        for name, sha in receipt['artifact_file_sha256'].items():
            self.assertEqual(sha, digest((RUN / name).read_bytes()))
        self.assertFalse(outputs['study-plan.json']['annotation_started'])
        self.assertFalse(outputs['study-plan.json']['reference_frozen_for_provider_scoring'])
        self.assertEqual(receipt['provider_requests'], 0)

    def test_assignments_balance_targets_conditions_and_positions(self):
        outputs = build()
        assignments = outputs['dispatch-plan.json']['assignments']
        target_cell, target_position, cell_position = Counter(), Counter(), Counter()
        tasks = set()
        self.assertEqual(len(assignments), 16)
        for assignment in assignments:
            rows = assignment['cases']
            self.assertEqual({r['case_id'] for r in rows}, {'probe-a', 'probe-b', 'probe-c', 'probe-d'})
            self.assertEqual({r['cell'] for r in rows}, {c['cell'] for c in CONDITIONS})
            packet = outputs[assignment['packet']]
            template = outputs[assignment['template']]
            for row, case, blank in zip(rows, packet['cases'], template['annotations']):
                self.assertEqual(row['case_id'], case['case_id'])
                target_cell[(row['case_id'], row['cell'])] += 1
                target_position[(row['case_id'], row['position'])] += 1
                cell_position[(row['cell'], row['position'])] += 1
                for key in ('case_id', 'state_sha256', 'task_sha256', 'rubric_sha256'):
                    self.assertEqual(case[key], blank[key])
                self.assertIsNone(blank['opportunity'])
                self.assertIsNone(blank['concern_kind'])
                self.assertEqual(case['state_sha256'], digest(canonical(case['state'])))
                self.assertEqual(case['task_sha256'], task_digest(case, packet))
                tasks.add(case['task_sha256'])
        self.assertEqual(len(tasks), 16)
        for counts in (target_cell, target_position, cell_position):
            self.assertEqual(len(counts), 16)
            self.assertEqual(set(counts.values()), {4})

    def test_only_names_change_and_literal_rule_addresses_are_preserved(self):
        source = 'class BDDPolicy:\n    value = "BDDPolicy"  # BDDPolicy remains a comment\n'
        result = rename_identifiers(source, {'BDDPolicy': 'RuleBase'})
        self.assertEqual(result, source.replace('class BDDPolicy:', 'class RuleBase:'))
        with self.assertRaisesRegex(ValueError, 'collide'):
            rename_identifiers('BDDPolicy = RuleBase\n', {'BDDPolicy': 'RuleBase'})
        outputs = build()
        audit = json.loads(AUDIT.read_text())
        mapping = outputs['source-mapping.json']
        packets = {case['task_sha256']: case for a in outputs['dispatch-plan.json']['assignments']
                   for case in outputs[a['packet']]['cases']}
        for binding in mapping['bindings']:
            case = packets[binding['task_sha256']]
            target = next(t for t in mapping['targets'] if t['target_id'] == case['case_id'])
            self.assertEqual(case['state']['target'], target['target'])
            for fragment, origin in zip(case['state']['bounded_context']['fragments'], binding['fragments']):
                original = audit['source_facts'][origin['source_fact']]['code']
                restored = fragment['code']
                if binding['neutral_owner_names']:
                    restored = rename_identifiers(restored, {v: k for k, v in binding['owner_renames'].items()})
                self.assertEqual(restored, original)
            if case['case_id'] == 'probe-a':
                code = '\n'.join(f['code'] for f in case['state']['bounded_context']['fragments'])
                self.assertIn('Specification[BDDContext]', code)
                self.assertIn('SG-RFC-0223.native.scenario-values', code)
                self.assertIn('not step.valid', code)
                self.assertEqual('class RuleBase(' in code, binding['neutral_owner_names'])

    def test_context_factor_is_additive_and_other_cases_cannot_reveal_textinput(self):
        outputs = build()
        for assignment in outputs['dispatch-plan.json']['assignments']:
            packet = outputs[assignment['packet']]
            for row, case in zip(assignment['cases'], packet['cases']):
                code = '\n'.join(f['code'] for f in case['state']['bounded_context']['fragments'])
                extended = next(c['additional_context'] for c in CONDITIONS if c['cell'] == row['cell'])
                self.assertEqual('class TextInput:' in code, case['case_id'] == 'probe-a' and extended)
                self.assertNotIn('contract-values', code)
                self.assertNotIn('Human approved', code)
                self.assertEqual(set(case), {'case_id', 'state', 'state_sha256', 'task_sha256', 'rubric_sha256'})
                self.assertTrue(all(f['fragment_id'].startswith('fragment-') for f in case['state']['bounded_context']['fragments']))
        bindings = outputs['source-mapping.json']['bindings']
        for target in ('probe-a', 'probe-b', 'probe-c', 'probe-d'):
            for small, large in (('01', '02'), ('03', '04')):
                low = next(b for b in bindings if b['case_id'] == target and b['cell'] == small)
                high = next(b for b in bindings if b['case_id'] == target and b['cell'] == large)
                self.assertEqual(low['fragments'], high['fragments'][:len(low['fragments'])])
                self.assertGreater(len(high['fragments']), len(low['fragments']))

    def test_real_validity_predicate_preserves_original_text_and_scalar_types(self):
        self.assertGreaterEqual(sys.version_info[:2], (3, 10), 'Pinned SpecGraph source requires Python >=3.10; use a matching virtual environment.')
        facts = json.loads(AUDIT.read_text())['source_facts']
        namespace = {'__name__': __name__}
        exec(compile(facts['focal-type-definition']['code'], '<pinned BDD types>', 'exec'), namespace)
        exec(compile(facts['focal-adapter']['code'], '<pinned BDD boundary>', 'exec'), namespace)
        for value, expected in [(None, False), (False, False), (42, False), ('', False),
                                (' \t\n', False), (' x ', True), ('x', True)]:
            with self.subTest(value=value):
                item = namespace['text'](value)
                self.assertEqual(item.valid, expected)
                self.assertEqual(item.value, value if isinstance(value, str) else None)
        entry = namespace['entry']({'id': 'A', 'steps': [' x ', 42, '']})
        self.assertEqual([s.valid for s in entry.steps], [True, False, False])
        self.assertEqual(entry.steps[0].value, ' x ')

    def test_prompt_formats_and_no_author_judgment_enters_packets(self):
        prompt = PROMPT.decode().format(directory='/tmp/assigned')
        self.assertIn('/tmp/assigned/packet.json', prompt)
        self.assertIn('/tmp/assigned/template.json', prompt)
        self.assertNotIn('{directory}', prompt)
        for name, packet in build().items():
            if name.startswith('packet-'):
                self.assertNotIn('hypotheses', packet)
                self.assertNotIn('owner_renames', json.dumps(packet))
                self.assertNotIn('recommended_pair', json.dumps(packet))

    def test_writer_refuses_overwrite_and_verifier_detects_artifact_drift(self):
        script = RUN.parents[1] / 'prepare_definition_owner_names.py'
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / 'rubric.json'
            sentinel.write_text('keep')
            result = subprocess.run([sys.executable, str(script), '--run', directory, '--write'], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(sentinel.read_text(), 'keep')
            self.assertEqual(list(Path(directory).iterdir()), [sentinel])
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(script), '--run', directory, '--write'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            verify(Path(directory))
            packet = Path(directory) / 'packet-annotator-01.json'
            packet.write_bytes(packet.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'differs'):
                verify(Path(directory))


if __name__ == '__main__':
    unittest.main()
