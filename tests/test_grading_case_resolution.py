"""Conservative matching between expected and reporter-produced test names."""

from swebench.harness.constants import TestStatus
from swebench.harness.grading import test_failed as grade_failed
from swebench.harness.grading import test_passed as grade_passed

PASSED = TestStatus.PASSED.value
FAILED = TestStatus.FAILED.value


def test_legacy_backslash_escaped_quotes_match_reporter_quotes():
    expected = r"External anchors use rel=\"noopener\""
    parsed = {'External anchors use rel="noopener"': PASSED}

    assert grade_passed(expected, parsed)
    assert not grade_failed(expected, parsed)


def test_quote_normalization_must_identify_one_key():
    expected = r"uses \"quoted\" input"
    parsed = {
        'uses "quoted" input': PASSED,
        r"uses \"quoted\" input": FAILED,
    }

    # The exact key wins even when its normalized spelling collides.
    assert not grade_passed(expected, parsed)
    assert grade_failed(expected, parsed)


def test_unique_suite_prefix_can_be_omitted_from_expected_name():
    expected = "builds throttling strings when simulate"
    parsed = {"util helpers - builds throttling strings when simulate": PASSED}

    assert grade_passed(expected, parsed)
    assert not grade_failed(expected, parsed)


def test_suite_suffix_match_must_be_unique_even_when_outcomes_agree():
    expected = ".enable() - should autoattach to root session"
    parsed = {
        "First suite - .enable() - should autoattach to root session": PASSED,
        "Second suite - .enable() - should autoattach to root session": PASSED,
    }

    assert not grade_passed(expected, parsed)
    assert grade_failed(expected, parsed)


def test_suite_suffix_requires_the_full_delimiter_boundary():
    expected = "target"
    parsed = {"suite-prefix-target": PASSED}

    assert not grade_passed(expected, parsed)
    assert grade_failed(expected, parsed)


def test_exact_name_wins_over_a_conflicting_suite_suffix():
    expected = "target"
    parsed = {"target": PASSED, "suite - target": FAILED}

    assert grade_passed(expected, parsed)
    assert not grade_failed(expected, parsed)
