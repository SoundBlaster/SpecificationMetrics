import unittest

import retrieval_fusion_replay_v2 as replay


class FusionRepairTests(unittest.TestCase):
    def test_unicode_words_and_identifiers_survive_tokenization(self):
        self.assertEqual(replay.unicode_tokens('Проверить ПОЛИТИКУ safeWorkspace_path 42'),
                         ['проверить', 'политику', 'safe', 'workspace', 'path', '42'])

    def test_zero_evidence_channel_cannot_override_dense_order(self):
        ids, dense = ['a', 'b', 'c', 'd'], [3, 2, 1, 0]
        self.assertNotEqual(replay.fuse([0, 0, 0, 0], dense, ids, positive_only=False), dense)
        self.assertEqual(replay.fuse([0, 0, 0, 0], dense, ids, positive_only=True), dense)

    def test_positive_lexical_evidence_still_contributes(self):
        self.assertEqual(replay.fuse([2, 0, 0], [1, 0, 2], ['a', 'b', 'c'], positive_only=True)[0], 0)

    def test_nonpositive_tail_does_not_add_votes(self):
        self.assertEqual(replay.fuse([-1, 0, -5], [2, 0, 1], ['a', 'b', 'c'], positive_only=True), [2, 0, 1])


if __name__ == '__main__':
    unittest.main()
