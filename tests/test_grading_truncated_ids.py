"""Regression tests for issue #290: truncated parametrized test ids.

SWE-bench_Verified contains 676 parametrized ids truncated mid-parameter
(unclosed bracket). Grading must tolerate them via unambiguous prefix
matching while preserving exact-match semantics for well-formed ids.
"""

from swebench.harness.constants import TestStatus
from swebench.harness.grading import test_failed as grade_failed
from swebench.harness.grading import test_passed as grade_passed

PASSED = TestStatus.PASSED.value
FAILED = TestStatus.FAILED.value
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


def test_xpass_is_a_passing_result():
    xpass = "XPASS"
    assert grade_passed("tests/test_a.py::test_x", {"tests/test_a.py::test_x": xpass})
    assert not grade_failed("tests/test_a.py::test_x", {"tests/test_a.py::test_x": xpass})


def test_failed_remains_a_failure():
    assert not grade_passed("tests/test_a.py::test_x", {"tests/test_a.py::test_x": FAILED})
    assert grade_failed("tests/test_a.py::test_x", {"tests/test_a.py::test_x": FAILED})
