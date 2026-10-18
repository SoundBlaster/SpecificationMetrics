from functools import partial
from importlib.metadata import PackageNotFoundError
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from coreinfra_transport import post
import rich_review_pilot_v2 as pilot
from structured_semantic_review_v1.preparation import load
from test_rich_review_pilot_v1 import Connection, response


class PreReservationRuntimeTests(unittest.TestCase):
    def setup_run(self, root):
        preparation, run = root / 'preparation', root / 'run'
        pilot.freeze(preparation)
        pilot.stage(preparation, run)
        return preparation, run

    def test_runtime_failure_does_not_burn_preparation_and_allows_a_corrected_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            preparation, run = self.setup_run(Path(directory))
            sender = Mock(side_effect=AssertionError('must not dispatch'))
            with patch.dict('os.environ', COREINFRA_API_KEY='offline-fixture'), \
                    patch.object(pilot, 'execution_runtime', side_effect=PackageNotFoundError('synthetic')):
                with self.assertRaises(PackageNotFoundError):
                    pilot.execute(preparation, run, live=True, sender=sender)
            sender.assert_not_called()
            self.assertFalse((preparation / 'dispatch-reservation.json').exists())
            self.assertEqual({p.name for p in run.iterdir()}, {'manifest.json', 'preparation-binding.json'})
            connection = Connection(response(pilot.selected()[2]))
            sender = partial(post, connection_factory=lambda timeout: connection)
            with patch.dict('os.environ', COREINFRA_API_KEY='offline-fixture'):
                receipt = pilot.execute(preparation, run, live=True, sender=sender)
            self.assertEqual(connection.posts, 1)
            self.assertTrue(receipt['http_body_received'])
            self.assertEqual(pilot.save_report(preparation, run)['status'], 'resolved_proposal')
            self.assertTrue(pilot.verify_result(preparation, run)['verified'])

    def test_post_reservation_failure_remains_diagnosable_and_cannot_be_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            preparation, run = self.setup_run(Path(directory))
            with patch.dict('os.environ', COREINFRA_API_KEY='offline-fixture'):
                receipt = pilot.execute(preparation, run, live=True, sender=Mock(side_effect=RuntimeError('synthetic')))
                self.assertEqual(receipt['stop_reason'], 'RuntimeError')
                self.assertTrue((preparation / 'dispatch-reservation.json').is_file())
                self.assertEqual(load((run / 'response.json').read_bytes())['status'], 'interrupted')
                with self.assertRaises(ValueError):
                    pilot.execute(preparation, run, live=True)

    def test_new_runner_cannot_consume_the_historical_v1_preparation(self):
        import rich_review_pilot_v1 as historical
        with self.assertRaises(ValueError):
            pilot.verify_preparation(historical.PREPARATION)
