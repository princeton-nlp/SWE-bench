"""pytest's ``SKIPPED [N] path:line: reason`` summary is not a test (#598).

All four pytest-family parsers in log_parsers/python.py had their own copy of the
loop, so all four recorded ``[N]`` as a fake test id.
"""

from swebench.harness.constants import TestStatus
from swebench.harness.log_parsers.python import (
    parse_log_matplotlib,
    parse_log_pytest,
    parse_log_pytest_options,
    parse_log_pytest_v2,
)

PASSED = TestStatus.PASSED.value

LOG = """SKIPPED [1] tests/test_a.py:12: needs network
PASSED tests/test_a.py::test_real
SKIPPED [23] tests/test_b.py:4: unsupported platform
"""


def test_skip_summary_excluded_from_all_pytest_parsers():
    for parser in (
        parse_log_pytest,
        parse_log_pytest_options,
        parse_log_pytest_v2,
        parse_log_matplotlib,
    ):
        result = parser(LOG, None)
        assert result == {"tests/test_a.py::test_real": PASSED}, parser.__name__


def test_genuine_skipped_test_is_still_recorded():
    """A real ``SKIPPED <nodeid>`` line must survive the guard."""
    log = "SKIPPED tests/test_a.py::test_flaky"
    assert parse_log_pytest(log, None) == {
        "tests/test_a.py::test_flaky": TestStatus.SKIPPED.value
    }


def test_wrapped_progress_artifact_is_dropped():
    """``PASSED [100%]`` is pytest's progress indicator wrapped onto its own
    line, not a test (#660). It used to be recorded because the gold PASS_TO_PASS
    of pytest-dev__pytest-5262/-7521 literally contained ``[100%]``; grading now
    tolerates that polluted label (see test_grading_progress_artifact_gold.py),
    so the parser can drop the artifact."""
    assert parse_log_pytest("PASSED [100%]", None) == {}
