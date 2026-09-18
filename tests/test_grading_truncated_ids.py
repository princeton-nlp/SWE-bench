"""Regression tests for issue #290: truncated parametrized test ids.

SWE-bench_Verified contains 676 parametrized ids truncated mid-parameter
(unclosed bracket). Grading must tolerate them via unambiguous prefix
matching while preserving exact-match semantics for well-formed ids.
"""

from swebench.harness.constants import TestStatus
from swebench.harness.grading import test_failed as grade_failed
from swebench.harness.grading import test_maintained as grade_maintained
from swebench.harness.grading import test_passed as grade_passed

PASSED = TestStatus.PASSED.value
FAILED = TestStatus.FAILED.value
SKIPPED = TestStatus.SKIPPED.value
XFAIL = TestStatus.XFAIL.value


def test_exact_match_still_exact():
    sm = {"tests/test_a.py::test_x[case-1]": PASSED}
    assert grade_passed("tests/test_a.py::test_x[case-1]", sm)
    assert not grade_failed("tests/test_a.py::test_x[case-1]", sm)


def test_missing_balanced_id_is_failed_no_fallback():
    """A well-formed id absent from the status map must NOT prefix-match."""
    sm = {"tests/test_a.py::test_x[case-1-extended]": PASSED}
    assert not grade_passed("tests/test_a.py::test_x[case-1]", sm)
    assert grade_failed("tests/test_a.py::test_x[case-1]", sm)


def test_truncated_id_unique_prefix_match():
    """The #290 shape: id cut mid-parameter, one matching full id."""
    truncated = "astropy/units/tests/test_format.py::test_ogip_grammar_fail[log(photon"
    full = truncated + " / m**2 s)]"
    sm = {full: PASSED}
    assert grade_passed(truncated, sm)
    assert not grade_failed(truncated, sm)


def test_truncated_id_no_match_is_failed():
    sm = {"tests/test_b.py::test_y[other]": PASSED}
    assert not grade_passed("tests/test_a.py::test_x[log(photon", sm)
    assert grade_failed("tests/test_a.py::test_x[log(photon", sm)


def test_truncated_id_ambiguous_same_status_ok():
    """Multiple prefix matches with identical status grade unambiguously."""
    truncated = "tests/test_a.py::test_x[args1-No"
    sm = {
        "tests/test_a.py::test_x[args1-None]": PASSED,
        "tests/test_a.py::test_x[args1-No-value]": PASSED,
    }
    assert grade_passed(truncated, sm)
    assert not grade_failed(truncated, sm)


def test_truncated_id_ambiguous_mixed_status_conservative():
    """Prefix matches with conflicting statuses stay unresolved (failed)."""
    truncated = "tests/test_a.py::test_x[args1-No"
    sm = {
        "tests/test_a.py::test_x[args1-None]": PASSED,
        "tests/test_a.py::test_x[args1-No-value]": FAILED,
    }
    assert not grade_passed(truncated, sm)
    assert grade_failed(truncated, sm)


def test_truncated_failed_id_reports_failed():
    truncated = "tests/test_a.py::test_x[log(photon"
    sm = {"tests/test_a.py::test_x[log(photon / m**2 s)]": FAILED}
    assert not grade_passed(truncated, sm)
    assert grade_failed(truncated, sm)


def test_mixed_passed_and_xfail_matches_resolve():
    """PASSED and XFAIL grade identically, so a mix is not ambiguous.

    Real case: scikit-learn__scikit-learn-15100 expects the truncated id
    ``test_callable_analyzer_error[file-AttributeError-'str'``, which prefix-
    matches three parametrizations -- two PASSED and one XFAIL.
    """
    truncated = (
        "tests/test_text.py::test_callable_analyzer_error[file-AttributeError-'str'"
    )
    sm = {
        truncated + " object has no attribute 'read'-CountVectorizer]": PASSED,
        truncated + " object has no attribute 'read'-TfidfVectorizer]": PASSED,
        truncated + " object has no attribute 'read'-HashingVectorizer]": XFAIL,
    }
    assert grade_passed(truncated, sm)
    assert not grade_failed(truncated, sm)


def test_surplus_closing_bracket_is_not_a_truncation():
    """Truncation only ever drops a ``]``, so a surplus ``]`` must not fall back.

    Guards the language-agnostic path: free-form JS/Java names may carry a stray
    bracket and must keep exact-match semantics.
    """
    case = "handles foo] gracefully"
    sm = {"handles foo] gracefully and more": PASSED}
    assert not grade_passed(case, sm)
    assert grade_failed(case, sm)


def test_truncated_p2p_matching_a_skip_and_a_failure_is_a_regression():
    """A skipped candidate must not stand in for a failed one.

    SKIPPED and FAILED are both non-passing, but they do not grade alike for a
    PASS_TO_PASS case: a skip is not a regression, a failure is. Resolving the
    pair to whichever the log listed first hides the failure.
    """
    truncated = "tests/test_a.py::test_x[a"
    sm = {
        "tests/test_a.py::test_x[a b]": SKIPPED,
        "tests/test_a.py::test_x[a c]": FAILED,
    }
    assert not grade_maintained(truncated, sm)
    assert grade_failed(truncated, sm)


def test_truncated_p2p_verdict_does_not_depend_on_log_order():
    truncated = "tests/test_a.py::test_x[a"
    skip_first = {
        "tests/test_a.py::test_x[a b]": SKIPPED,
        "tests/test_a.py::test_x[a c]": FAILED,
    }
    fail_first = {
        "tests/test_a.py::test_x[a c]": FAILED,
        "tests/test_a.py::test_x[a b]": SKIPPED,
    }
    assert grade_maintained(truncated, skip_first) == grade_maintained(
        truncated, fail_first
    )


def test_truncated_p2p_all_skipped_is_still_maintained():
    """Skip-only matches agree, so the existing tolerance is unchanged."""
    truncated = "tests/test_a.py::test_x[a"
    sm = {
        "tests/test_a.py::test_x[a b]": SKIPPED,
        "tests/test_a.py::test_x[a c]": SKIPPED,
    }
    assert grade_maintained(truncated, sm)


def test_truncated_id_failed_and_error_still_resolve():
    """FAILED and ERROR grade alike, so a mix of the two stays unambiguous."""
    truncated = "tests/test_a.py::test_x[a"
    sm = {
        "tests/test_a.py::test_x[a b]": FAILED,
        "tests/test_a.py::test_x[a c]": TestStatus.ERROR.value,
    }
    assert grade_failed(truncated, sm)
    assert not grade_passed(truncated, sm)
