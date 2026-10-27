import copy
import io
from contextlib import redirect_stderr
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import run


class RunnerIntegrityTests(unittest.TestCase):
    def test_changed_or_empty_matrix_cannot_be_successful_empty_run(self):
        with patch.object(Path, "read_bytes", return_value=b'{"unit_cases": []}'):
            with self.assertRaisesRegex(ValueError, "matrix changed"):
                run.load_matrix(Path("unused"))

    def test_duplicate_case_is_not_counted_twice(self):
        _, matrix = run.load_matrix(run.ROOT / "docs/local-alias-flow-cases.json")
        matrix = copy.deepcopy(matrix)
        matrix["unit_cases"].append(matrix["unit_cases"][0])
        with self.assertRaisesRegex(ValueError, "duplicate unit ID"):
            run.unit_results(matrix)

    def test_output_inside_checkout_is_rejected_before_inspection(self):
        argv = ["run.py", "--output", str(run.ROOT / "unused-run")]
        with patch.object(sys, "argv", argv), redirect_stderr(io.StringIO()):
            with patch.object(run, "load_matrix") as load:
                with self.assertRaises(SystemExit) as error:
                    run.main()
                self.assertEqual(error.exception.code, 2)
                load.assert_not_called()

    def test_source_enum_precondition_does_not_accept_arbitrary_class(self):
        with self.assertRaisesRegex(ValueError, "import/class fact unavailable"):
            run.enum_preconditions(
                "class _AcceptanceCriterionDisposition:\n    ADD_PLACEHOLDER = 1\n",
                "specgraph-02",
            )


if __name__ == "__main__":
    unittest.main()
