"""Results emitted outside the START/END markers must still be graded (#402).

`set -x` traces the marker no-ops to stderr, so depending on how a runner
interleaves stdout and stderr the results can land outside them. Slicing then
yields nothing and the run looks resultless -- fastlane__fastlane-21857 in
SWE-bench_Multilingual fails this way (208 chars inside the markers, 3 real
results outside them).
"""

from swebench.harness.constants import (
    END_TEST_OUTPUT,
    START_TEST_OUTPUT,
    TEST_EXIT_CODE,
)
from swebench.harness.grading import get_logs_eval
from swebench.types import TestSpec


def _spec(**kw):
    return TestSpec(
        **{
            "instance_id": "x__x-1",
            "image": "x:latest",
            "eval_script_list": [],
            "repo": "x/x",
            "version": "1.0",
            "FAIL_TO_PASS": [],
            "PASS_TO_PASS": [],
            "log_parser": "parse_log_pytest",
            "eval_type": "pass_and_fail",
            **kw,
        }
    )


def test_results_inside_markers_are_used(tmp_path):
    log = tmp_path / "test_output.txt"
    log.write_text(
        f"{START_TEST_OUTPUT}\nPASSED tests/test_a.py::test_in\n{END_TEST_OUTPUT}\n"
    )
    sm, found = get_logs_eval(_spec(), str(log))
    assert found and sm == {"tests/test_a.py::test_in": "PASSED"}


def test_results_outside_markers_fall_back_to_whole_log(tmp_path):
    """Empty between the markers, real results outside -> use the whole log."""
    log = tmp_path / "test_output.txt"
    log.write_text(
        f"PASSED tests/test_a.py::test_outside\n{START_TEST_OUTPUT}\n{END_TEST_OUTPUT}\n"
    )
    sm, found = get_logs_eval(_spec(), str(log))
    assert found and sm == {"tests/test_a.py::test_outside": "PASSED"}


def test_missing_markers_still_reports_not_found(tmp_path):
    log = tmp_path / "test_output.txt"
    log.write_text("PASSED tests/test_a.py::test_x\n")
    sm, found = get_logs_eval(_spec(), str(log))
    assert (sm, found) == ({}, False)


def test_empty_results_without_evidence_is_not_found(tmp_path):
    """A suite that never ran must not grade as a pass.

    Under EvalType.FAIL_ONLY an absent test counts as success, so an empty status
    map with no sign the runner executed would score every F2P test as resolved --
    which is how 73 openlayers instances "passed" with Chrome failing to launch.
    """
    log = tmp_path / "test_output.txt"
    log.write_text(
        f"{START_TEST_OUTPUT}\nChrome failed 2 times (cannot start). Giving up.\n"
        f"{END_TEST_OUTPUT}\n"
    )
    assert get_logs_eval(_spec(), str(log)) == ({}, False)


def test_empty_results_with_runner_evidence_is_a_clean_run(tmp_path):
    """Karma prints only failures, so 'ran, no failures' is a legitimate empty map."""
    log = tmp_path / "test_output.txt"
    log.write_text(
        f"{START_TEST_OUTPUT}\nExecuted 1339 of 1346 (skipped 7) SUCCESS\n"
        f"TOTAL: 1339 SUCCESS\n{END_TEST_OUTPUT}\n"
    )
    sm, found = get_logs_eval(_spec(), str(log))
    assert (sm, found) == ({}, True)


def test_a_clean_jasmine_run_counts_as_having_run(tmp_path):
    """marked's parser records failures only, so a passing suite parses to nothing.

    Without positive evidence the suite ran, such a run is rejected and the
    instance grades unresolved even though every test passed -- 14 markedjs
    instances in SWE-bench_Multimodal dev fail this way.
    """
    log = tmp_path / "test_output.txt"
    log.write_text(
        f"{START_TEST_OUTPUT}\nStarted\n.....\n\n658 specs, 0 failures\n{END_TEST_OUTPUT}\n"
    )
    sm, found = get_logs_eval(
        _spec(log_parser="parse_log_marked", eval_type="fail_only"), str(log)
    )
    assert found and sm == {}


def test_a_suite_that_never_started_is_still_rejected(tmp_path):
    log = tmp_path / "test_output.txt"
    log.write_text(f"{START_TEST_OUTPUT}\nbrowser failed to launch\n{END_TEST_OUTPUT}\n")
    sm, found = get_logs_eval(
        _spec(log_parser="parse_log_marked", eval_type="fail_only"), str(log)
    )
    assert not found


def test_jasmine_suite_error_with_nonzero_exit_is_not_found(tmp_path):
    """A suite-level failure records no per-test failure but exits non-zero.

    Jasmine prints an afterAll failure as an unnumbered "Suite error:" block, so
    parse_log_marked returns an empty map even though the runner reports
    "1 spec, 1 failure" and exits 1. The recorded exit code is the only signal
    that something failed; without it the empty map grades resolved under
    fail_only (#686).
    """
    log = tmp_path / "test_output.txt"
    log.write_text(
        f"{START_TEST_OUTPUT}\nStarted\n.\n\n\n"
        "Suite error: evaluation reproduction\n"
        "  Message:\n    Error: suite teardown failed\n\n"
        f"1 spec, 1 failure\n{END_TEST_OUTPUT}\n{TEST_EXIT_CODE}: 1\n"
    )
    sm, found = get_logs_eval(
        _spec(log_parser="parse_log_marked", eval_type="fail_only"), str(log)
    )
    assert (sm, found) == ({}, False)


def test_clean_jasmine_run_with_zero_exit_is_still_found(tmp_path):
    """The empty-map rejection above must not swallow clean Jasmine runs."""
    log = tmp_path / "test_output.txt"
    log.write_text(
        f"{START_TEST_OUTPUT}\nStarted\n.\n\n1 spec, 0 failures\n"
        f"{END_TEST_OUTPUT}\n{TEST_EXIT_CODE}: 0\n"
    )
    sm, found = get_logs_eval(
        _spec(log_parser="parse_log_marked", eval_type="fail_only"), str(log)
    )
    assert (sm, found) == ({}, True)


def test_a_zero_count_summary_is_not_evidence_the_suite_ran(tmp_path):
    """karma prints "Executed 0 of 0" when it loses the browser before any test.

    Under fail_only an empty status map scores every F2P test as passing, so
    accepting a zero count resolves an instance whose suite never ran --
    chartjs__Chart.js-9678 passed 24/24 this way with no tests executed.
    """
    log = tmp_path / "test_output.txt"
    log.write_text(
        f"{START_TEST_OUTPUT}\nChrome 120: Executed 0 of 0 DISCONNECTED\n{END_TEST_OUTPUT}\n"
    )
    sm, found = get_logs_eval(
        _spec(log_parser="parse_log_chart_js", eval_type="fail_only"), str(log)
    )
    assert not found


def test_a_real_karma_run_is_still_evidence(tmp_path):
    log = tmp_path / "test_output.txt"
    log.write_text(
        f"{START_TEST_OUTPUT}\nChrome 120: Executed 294 of 1293 SUCCESS\n{END_TEST_OUTPUT}\n"
    )
    sm, found = get_logs_eval(
        _spec(log_parser="parse_log_chart_js", eval_type="fail_only"), str(log)
    )
    assert found and sm == {}
