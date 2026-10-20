"""Tests for parse_log_pytest_v2 (used by astropy, scikit-learn, sphinx).

Covers #279: pytest ids may contain spaces, so the id is the whole remainder of
the line rather than a single token.
"""

from swebench.harness.constants import TestStatus
from swebench.harness.log_parsers.python import parse_log_pytest_v2

PASSED = TestStatus.PASSED.value
FAILED = TestStatus.FAILED.value


def test_id_containing_spaces_is_not_split():
    log = "PASSED astropy/units/tests/test_format.py::test_unicode[m⁻\xb9-unit3 extra]"
    result = parse_log_pytest_v2(log, None)
    assert result == {
        "astropy/units/tests/test_format.py::test_unicode[m⁻\xb9-unit3 extra]": PASSED
    }


def test_trailing_status_form_keeps_spaces():
    log = "tests/test_a.py::test_x[a b] PASSED"
    assert parse_log_pytest_v2(log, None) == {"tests/test_a.py::test_x[a b]": PASSED}


def test_failed_assertion_message_excluded_from_id():
    """The " - <message>" suffix must not become part of the test id."""
    log = "FAILED tests/test_a.py::test_x[a b] - AssertionError: expected 1 got 2"
    assert parse_log_pytest_v2(log, None) == {"tests/test_a.py::test_x[a b]": FAILED}


def test_bare_status_line_is_skipped():
    """A status word alone must not insert an empty-string key (cf. #611)."""
    log = "PASSED\nFAILED\ntests/test_a.py::test_y PASSED"
    result = parse_log_pytest_v2(log, None)
    assert "" not in result
    assert result == {"tests/test_a.py::test_y": PASSED}


def test_ansi_coloring_still_stripped():
    log = "\x1b[32mPASSED\x1b[0m tests/test_a.py::\x1b[1mtest_z\x1b[0m"
    assert parse_log_pytest_v2(log, None) == {"tests/test_a.py::test_z": PASSED}


def test_xpass_is_preserved():
    from swebench.harness.log_parsers.python import parse_log_pytest

    log = "XPASS tests/test_a.py::test_expected_failure - condition now holds"
    expected = {"tests/test_a.py::test_expected_failure": "XPASS"}

    assert parse_log_pytest(log, None) == expected
    assert parse_log_pytest_v2(log, None) == expected
