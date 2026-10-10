"""Gold labels polluted with pytest progress artifacts grade as if absent (#660).

Dataset build captured ``PASSED [100%]`` as the test id ``[100%]`` in the gold
PASS_TO_PASS of pytest-dev__pytest-5262 (108 P2P entries, one is ``[100%]``)
and pytest-dev__pytest-7521 (125 entries, same). The parser now drops the
artifact, so the id goes missing from the eval status map -- and a missing P2P
test is graded as a failure. These tests pin the transitional tolerance in
get_eval_tests_report that ignores such ids until swe-bench-tasks repairs the
gold lists (mirrors the truncated-ids tolerance in ``_resolve_case``, #290).
"""

import pytest

from swebench.harness.constants import (
    FAIL_TO_PASS,
    PASS_TO_PASS,
    EvalType,
    ResolvedStatus,
    TestStatus,
)
from swebench.harness.grading import get_eval_tests_report, get_resolution_status

PASSED = TestStatus.PASSED.value
FAILED = TestStatus.FAILED.value


def _gold(f2p, p2p):
    return {
        FAIL_TO_PASS: f2p,
        PASS_TO_PASS: p2p,
    }


def test_phantom_p2p_entry_does_not_fail_resolution():
    """The exact pytest-5262/7521 shape: gold P2P holds ``[100%]``, the parsed
    map (from the fixed parser) does not. Every real test passed, so the
    instance must resolve."""
    sm = {"test_a": PASSED, "test_b": PASSED}
    report = get_eval_tests_report(
        sm, _gold([], ["test_a", "test_b", "[100%]"]), eval_type=EvalType.PASS_AND_FAIL
    )
    assert report[PASS_TO_PASS]["failure"] == []
    assert get_resolution_status(report) == ResolvedStatus.FULL.value


def test_phantom_f2p_entry_does_not_fail_resolution():
    sm = {"test_a": PASSED}
    report = get_eval_tests_report(
        sm, _gold(["test_a", "[100%]"], []), eval_type=EvalType.PASS_AND_FAIL
    )
    assert report[FAIL_TO_PASS]["failure"] == []
    assert get_resolution_status(report) == ResolvedStatus.FULL.value


def test_tolerance_does_not_mask_real_failures():
    """Only the artifact ids are forgiven; a genuinely failing test still fails
    the instance."""
    sm = {"test_a": PASSED, "test_b": FAILED}
    report = get_eval_tests_report(
        sm, _gold(["test_a"], ["test_b", "[100%]"]), eval_type=EvalType.PASS_AND_FAIL
    )
    assert report[PASS_TO_PASS]["failure"] == ["test_b"]
    assert get_resolution_status(report) == ResolvedStatus.NO.value


def test_phantom_recorded_as_passing_is_still_ignored():
    """Even if an old log still parses a phantom entry, the polluted gold id is
    dropped before matching, so grading does not depend on the artifact."""
    sm = {"test_a": PASSED, "test_b": PASSED, "[100%]": PASSED}
    report = get_eval_tests_report(
        sm, _gold([], ["test_a", "test_b", "[100%]"]), eval_type=EvalType.PASS_AND_FAIL
    )
    assert report[PASS_TO_PASS]["success"] == ["test_a", "test_b"]
    assert get_resolution_status(report) == ResolvedStatus.FULL.value


def test_clean_gold_lists_are_untouched():
    """The tolerance must not change grading for well-formed instances."""
    sm = {"test_a": PASSED, "test_b": PASSED, "test_c": FAILED}
    report = get_eval_tests_report(
        sm, _gold(["test_a"], ["test_b"]), eval_type=EvalType.PASS_AND_FAIL
    )
    assert report[FAIL_TO_PASS]["success"] == ["test_a"]
    assert report[PASS_TO_PASS]["success"] == ["test_b"]
    assert get_resolution_status(report) == ResolvedStatus.FULL.value


@pytest.mark.parametrize(
    "bad_id", ["[100%]", "[ 42%]", "[", "42%]", "[1]", "[  3%]"]
)
def test_known_artifact_shapes_are_tolerated_in_p2p(bad_id):
    """The family of fragments pytest's wrapped, whitespace-split progress
    indicator produces; none may doom an instance."""
    sm = {"test_a": PASSED}
    report = get_eval_tests_report(
        sm, _gold([], ["test_a", bad_id]), eval_type=EvalType.PASS_AND_FAIL
    )
    assert get_resolution_status(report) == ResolvedStatus.FULL.value


def test_fail_only_eval_type_still_fails_on_real_failure():
    sm = {"test_a": PASSED, "test_b": FAILED}
    report = get_eval_tests_report(
        sm, _gold(["test_a"], ["test_b", "[100%]"]), eval_type=EvalType.FAIL_ONLY
    )
    assert get_resolution_status(report) == ResolvedStatus.NO.value
