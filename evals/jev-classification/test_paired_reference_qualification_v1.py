from pathlib import Path
import tempfile
import unittest

from coreinfra_retry_run import decode, sha
from paired_reference_qualification_v1 import freeze, qualify, verify
from retrieval_index_v1.source import encoded


class QualificationTests(unittest.TestCase):
    def test_eight_valid_annotations_do_not_qualify_as_balanced_paired_reference(self):
        result = qualify()
        self.assertTrue(result['integrity_verified'])
        self.assertEqual((result['actual_annotators'], result['balanced_actual_annotators']), (8, 0))
        self.assertTrue(result['diagnostic_labels_available'])
        self.assertFalse(result['paired_quality_scoring_allowed'])
        self.assertFalse(result['inference_authorized'])

    def test_authority_cannot_be_promoted_by_rebinding_json_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'qualification'
            freeze(output)
            self.assertEqual(verify(output), qualify())
            path = output / 'qualification.json'
            value = decode(path.read_bytes())
            value['paired_quality_scoring_allowed'] = True
            path.write_text(encoded(value))
            receipt_path = output / 'receipt.json'
            receipt = decode(receipt_path.read_bytes())
            receipt['file_sha256']['qualification.json'] = sha(path.read_bytes())
            receipt_path.write_text(encoded(receipt))
            with self.assertRaises(ValueError):
                verify(output)


if __name__ == '__main__':
    unittest.main()
