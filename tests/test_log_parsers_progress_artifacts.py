"""pytest's wrapped progress indicator is not a test (#660).

When a node id overflows the terminal width, pytest wraps the trailing
``[NN%]`` onto the next line together with the status word::

    testing/test_long.py::test_a_very_long_node_id_that_overflows
    PASSED [100%]

Every pytest-family parser recorded the first non-status token as a test id,
inventing ``[100%]`` (and, for pytest's right-aligned ``[ 42%]`` split across
tokens, ``[``). Dataset build then copied the artifact into gold labels --
pytest-dev__pytest-5262 and -7521 literally expect ``[100%]`` in PASS_TO_PASS.
"""

import re

import pytest

from swebench.harness.constants import TestStatus
from swebench.harness.log_parsers.python import (
    is_progress_artifact_id,
    parse_log_matplotlib,
    parse_log_pytest,
    parse_log_pytest_options,
    parse_log_pytest_v2,
)

PASSED = TestStatus.PASSED.value
FAILED = TestStatus.FAILED.value
SKIPPED = TestStatus.SKIPPED.value
XFAIL = TestStatus.XFAIL.value

PYTEST_PARSERS = [
    parse_log_pytest,
    parse_log_pytest_options,
    parse_log_pytest_v2,
    parse_log_matplotlib,
]

REAL_ID = "testing/test_a.py::test_real"


@pytest.mark.parametrize("parser", PYTEST_PARSERS, ids=lambda p: p.__name__)
@pytest.mark.parametrize(
    "artifact_line",
    [
        "PASSED [100%]",  # the shape captured into gold PASS_TO_PASS (#660)
        "PASSED [ 42%]",  # right-aligned percentage splits into "[", "42%]"
        "PASSED [  2%]",
        "FAILED [ 99%]",
        "ERROR [  1%]",
        "XFAIL [100%]",
    ],
)
def test_wrapped_progress_line_yields_no_test(parser, artifact_line):
    assert parser(artifact_line, None) == {}


@pytest.mark.parametrize("parser", PYTEST_PARSERS, ids=lambda p: p.__name__)
def test_wrapped_progress_between_real_results(parser):
    """A wrapped status line inside a short-summary block must not disturb the
    real results around it."""
    log = f"""\
SKIPPED [1] testing/conftest.py:12: needs network
{PASSED} {REAL_ID}
PASSED [100%]
FAILED testing/test_a.py::test_broken - assert 0 == 1
PASSED [ 42%]
"""
    assert parser(log, None) == {
        REAL_ID: PASSED,
        "testing/test_a.py::test_broken": FAILED,
    }


def test_nodeid_first_verbose_lines_stay_ignored():
    """``nodeid PASSED [100%]`` never entered the status-first branch and still
    must not: the change only drops status-only artifacts."""
    assert parse_log_pytest(f"{REAL_ID} PASSED [100%]", None) == {}


@pytest.mark.parametrize("parser", PYTEST_PARSERS, ids=lambda p: p.__name__)
def test_parametrized_ids_are_preserved(parser):
    """Bracketed ids with a real path must survive the artifact guard."""
    log = f"""\
PASSED testing/test_a.py::test_foo[param-1]
PASSED testing/test_a.py::test_foo[param-2]
FAILED testing/test_a.py::test_bar[3%] - assert 0
"""
    assert parser(log, None) == {
        "testing/test_a.py::test_foo[param-1]": PASSED,
        "testing/test_a.py::test_foo[param-2]": PASSED,
        "testing/test_a.py::test_bar[3%]": FAILED,
    }


def test_options_parser_still_normalizes_absolute_params():
    """The option normalization in parse_log_pytest_options is untouched by the
    artifact guard."""
    assert parse_log_pytest_options(
        "PASSED testing/test_a.py::test_file[/abs/path/name]", None
    ) == {"testing/test_a.py::test_file[/name]": PASSED}


def test_genuine_skipped_test_is_still_recorded():
    """A real ``SKIPPED <nodeid>`` line must survive the skip-summary guard."""
    assert parse_log_pytest("SKIPPED testing/test_a.py::test_flaky", None) == {
        "testing/test_a.py::test_flaky": SKIPPED
    }


def test_skip_summary_still_dropped():
    assert parse_log_pytest("SKIPPED [1] testing/conftest.py:12: needs network", None) == {}


def test_synthetic_session_matches_gold_without_phantoms():
    """End-to-end fixture: a verbose block with two wrapped progress lines plus
    a ``-rA`` short summary, the shape that produced the polluted gold label.
    The parsed map must equal exactly the real short-summary results."""
    log = """\
============================= test session starts ==============================
collected 108 items

testing/test_long.py::test_first_very_long_node_id_that_wraps_the_progress_indicator
PASSED [  3%]
testing/test_short.py::test_second PASSED [100%]

=========================== short test summary info ============================
PASSED testing/test_long.py::test_first_very_long_node_id_that_wraps_the_progress_indicator
PASSED testing/test_short.py::test_second
========================= 2 passed in 0.42s =========================
"""
    assert parse_log_pytest(log, None) == {
        "testing/test_long.py::test_first_very_long_node_id_that_wraps_the_progress_indicator": PASSED,
        "testing/test_short.py::test_second": PASSED,
    }


@pytest.mark.parametrize(
    "test_id, expected",
    [
        ("[100%]", True),
        ("[ 42%]", True),
        ("[", True),
        ("42%]", True),
        ("[1]", True),
        (REAL_ID, False),
        ("testing/test_a.py::test_bar[3%]", False),
        ("test_a.py:12", False),
        ("", False),
    ],
)
def test_is_progress_artifact_id(test_id, expected):
    assert is_progress_artifact_id(test_id) is expected


def test_no_regression_in_real_ids_across_matrix():
    """Whatever the parsers record must always carry a node-id path: the artifact
    guard cannot have eaten a genuine result."""
    log = "\n".join(
        [
            f"PASSED {REAL_ID}",
            "PASSED [100%]",
            "SKIPPED [2] testing/conftest.py:3: xfail-ish",
            "SKIPPED testing/test_a.py::test_skipped",
            "XFAILED testing/test_a.py::test_xfail",
        ]
    )
    for parser in PYTEST_PARSERS:
        result = parser(log, None)
        assert result, parser.__name__
        for test_id in result:
            assert "::" in test_id or re.search(r"[A-Za-z_]", test_id), (
                f"{parser.__name__} recorded a non-path id: {test_id!r}"
            )
        assert result.get(REAL_ID) == PASSED, parser.__name__
