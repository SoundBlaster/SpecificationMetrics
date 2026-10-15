import copy
import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from retrieval_index_v1.source import digest, snapshot
from retrieval_index_v1.store import plan, read_current, update

PROFILE = dict(model='test-only', revision='a' * 40, dimensions=2, document_prompt='',
               normalize=True, runtime={'test': '1'}, model_files_sha256='b' * 64)
CODE = '''def allowed(value):
    # Domain premise.
    ready = value > 0
    return ready

Rule = PredicateSpec(
    allowed,
    name="allowed",
)

def unrelated(value):
    # Independent fragment.
    result = str(value)
    return result
'''


class IncrementalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.store = self.root / 'index.sqlite'
        self.git('init', '-q')
        self.git('config', 'user.name', 'Index test')
        self.git('config', 'user.email', 'index@example.invalid')
        (self.repo / 'tools').mkdir()
        self.path = self.repo / 'tools/policy.py'
        self.commit(CODE)
        self.calls = []

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.PIPE)

    def commit(self, text=None):
        if text is not None:
            self.path.write_text(text)
        self.git('add', '-A')
        self.git('commit', '-qm', 'fixture', '--allow-empty')

    def source(self, **kwargs):
        return snapshot(self.repo, 'fixture', **kwargs)

    def encode(self, texts):
        self.calls.extend(texts)
        return [[1.0, 0.0] for _ in texts]

    def test_first_update_and_noop_do_not_reencode(self):
        source = self.source()
        self.assertEqual(plan(self.store, source, PROFILE)['encode_inputs'], 3)
        self.assertFalse(self.store.exists())
        first = update(self.store, source, PROFILE, self.encode)
        second = update(self.store, source, PROFILE, self.encode)
        self.assertEqual(first['encode_inputs'], 3)
        self.assertEqual(second['encode_inputs'], 0)
        self.assertEqual(second['reused_documents'], 3)
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(len(read_current(self.store, source, PROFILE)), 3)

    def test_helper_change_reencodes_both_helper_and_spec(self):
        update(self.store, self.source(), PROFILE, self.encode)
        self.commit(CODE.replace('value > 0', 'value > 10'))
        changed = update(self.store, self.source(), PROFILE, self.encode)
        self.assertEqual((changed['changed'], changed['encode_inputs'], changed['reused_documents']), (2, 2, 1))
        self.assertTrue(any('# Local predicate: allowed' in text for text in self.calls[-2:]))

    def test_line_shift_refreshes_provenance_without_encoding(self):
        before = self.source()
        update(self.store, before, PROFILE, self.encode)
        self.commit('# leading comment\n' + CODE)
        after = self.source()
        with self.assertRaisesRegex(ValueError, 'stale'):
            read_current(self.store, after, PROFILE)
        result = update(self.store, after, PROFILE, self.encode)
        self.assertEqual(result['encode_inputs'], 0)
        docs = read_current(self.store, after, PROFILE)
        self.assertTrue(all(d['source']['revision'] == after['revision'] for d in docs))
        self.assertEqual(docs[0]['source']['start_line'], before['documents'][0]['source']['start_line'] + 1)

    def test_deletion_rename_and_restore_have_no_ghost_results(self):
        before = self.source()
        update(self.store, before, PROFILE, self.encode)
        self.path.rename(self.repo / 'tools/renamed.py')
        self.commit()
        renamed = self.source()
        result = update(self.store, renamed, PROFILE, self.encode)
        self.assertEqual((result['added'], result['removed'], result['encode_inputs']), (3, 3, 3))
        self.assertTrue(all(d['source']['path'] == 'tools/renamed.py' for d in read_current(self.store, renamed, PROFILE)))
        (self.repo / 'tools/renamed.py').unlink()
        self.commit()
        empty = self.source()
        result = update(self.store, empty, PROFILE, self.encode)
        self.assertEqual((result['removed'], result['encode_inputs']), (3, 0))
        self.assertEqual(read_current(self.store, empty, PROFILE), [])
        result = update(self.store, before, PROFILE, self.encode)
        self.assertEqual(result['encode_inputs'], 0)  # retained cache permits explicit historical rebuild

    def test_revision_scope_and_profile_are_required_at_read_boundary(self):
        source = self.source()
        update(self.store, source, PROFILE, self.encode)
        self.commit()  # Same source bytes, different revision.
        with self.assertRaisesRegex(ValueError, 'stale'):
            read_current(self.store, self.source(), PROFILE)
        with self.assertRaisesRegex(ValueError, 'stale'):
            read_current(self.store, self.source(excludes=('tools/*',)), PROFILE)
        changed = dict(PROFILE, document_prompt='passage: ')
        with self.assertRaisesRegex(ValueError, 'stale'):
            read_current(self.store, source, changed)
        result = update(self.store, source, changed, self.encode)
        self.assertEqual(result['encode_inputs'], 3)

    def test_model_and_runtime_change_invalidates_cache(self):
        source = self.source()
        update(self.store, source, PROFILE, self.encode)
        for change in [dict(revision='c' * 40), dict(model_files_sha256='d' * 64), dict(runtime={'test': '2'})]:
            profile = dict(PROFILE, **change)
            self.assertEqual(plan(self.store, source, profile)['encode_inputs'], 3)

    def test_failure_rolls_back_cache_and_active_snapshot(self):
        before = self.source()
        update(self.store, before, PROFILE, self.encode)
        self.commit(CODE.replace('value > 0', 'value > 10') + '\n' + CODE.replace('allowed', 'other').replace('Rule', 'OtherRule').replace('unrelated', 'other_unrelated'))
        after = self.source()
        batches = []

        def fail_second_batch(texts):
            batches.append(texts)
            if len(batches) > 1:
                raise RuntimeError('interrupted encoding')
            return self.encode(texts)

        with self.assertRaisesRegex(RuntimeError, 'interrupted'):
            update(self.store, after, PROFILE, fail_second_batch)
        self.assertEqual(len(read_current(self.store, before, PROFILE)), 3)
        self.assertEqual(plan(self.store, after, PROFILE)['encode_inputs'], 5)

    def test_invalid_vector_or_count_never_publishes(self):
        source = self.source()
        update(self.store, source, PROFILE, self.encode)
        changed = dict(PROFILE, revision='c' * 40)
        for bad in [[], [[1.0]], [[float('nan'), 0.0]] * 3, [[0.0, 0.0]] * 3, [[True, 0.0]] * 3]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                update(self.store, source, changed, lambda texts: bad)
            self.assertEqual(len(read_current(self.store, source, PROFILE)), 3)

    def test_cache_corruption_is_not_reused(self):
        source = self.source()
        update(self.store, source, PROFILE, self.encode)
        with sqlite3.connect(self.store) as db:
            db.execute("UPDATE vectors SET value='[0.0,1.0]'")
        with self.assertRaisesRegex(ValueError, 'checksum'):
            plan(self.store, source, PROFILE)
        with self.assertRaisesRegex(ValueError, 'checksum'):
            read_current(self.store, source, PROFILE)

    def test_incomplete_manifest_is_not_readable_even_with_valid_checksum(self):
        source = self.source()
        update(self.store, source, PROFILE, self.encode)
        with sqlite3.connect(self.store) as db:
            manifest = json.loads(db.execute('SELECT value FROM active').fetchone()[0])
            manifest['status'] = 'building'
            raw = json.dumps(manifest)
            db.execute('UPDATE active SET value=?, sha256=?', (raw, digest(raw)))
        with self.assertRaisesRegex(ValueError, 'not a complete'):
            read_current(self.store, source, PROFILE)

    def test_reader_sees_old_complete_snapshot_while_new_vectors_are_encoded(self):
        before = self.source()
        update(self.store, before, PROFILE, self.encode)
        self.commit(CODE.replace('value > 0', 'value > 10'))
        after = self.source()

        def read_during_encode(texts):
            self.assertEqual(len(read_current(self.store, before, PROFILE)), 3)
            with self.assertRaisesRegex(ValueError, 'stale'):
                read_current(self.store, after, PROFILE)
            return self.encode(texts)

        update(self.store, after, PROFILE, read_during_encode)
        self.assertEqual(len(read_current(self.store, after, PROFILE)), 3)

    def test_empty_initial_snapshot_is_valid_and_dirty_tree_is_excluded(self):
        committed = self.source()
        self.path.write_text('this is not Python')
        self.assertEqual(self.source(), committed)
        empty = self.source(excludes=('tools/*',))
        self.assertEqual(update(self.store, empty, PROFILE, self.encode)['encode_inputs'], 0)
        self.assertEqual(read_current(self.store, empty, PROFILE), [])

    def test_source_parse_failure_keeps_old_index(self):
        before = self.source()
        update(self.store, before, PROFILE, self.encode)
        self.commit('def broken(\n')
        with self.assertRaises(SyntaxError):
            self.source()
        self.assertEqual(len(read_current(self.store, before, PROFILE)), 3)

    def test_repository_mismatch_and_duplicate_symbols_are_rejected(self):
        source = self.source()
        update(self.store, source, PROFILE, self.encode)
        wrong = copy.deepcopy(source)
        wrong['repository_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'different repository'):
            update(self.store, wrong, PROFILE, self.encode)
        self.commit(CODE + '\n' + CODE)
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            self.source()

    def test_selected_symlink_is_not_followed(self):
        (self.repo / 'tools/link.py').symlink_to('policy.py')
        self.commit()
        with self.assertRaisesRegex(ValueError, 'unsupported source'):
            self.source()


if __name__ == '__main__':
    unittest.main()
