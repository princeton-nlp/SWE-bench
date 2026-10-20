"""Infrastructure-failure classification must not touch the scoring denominator (#586).

The original approach in #594 routed infra failures out of both `resolved_ids` and
`unresolved_ids`, so any misclassified instance silently left the denominator and
inflated scores. These tests pin the additive behavior instead.
"""

import json

from swebench.harness import reporting
from swebench.harness.constants import (
    LOG_INSTANCE,
    LOG_REPORT,
    LOG_TEST_OUTPUT,
)
from swebench.harness.infra_failure import (
    TIER_AMBIGUOUS,
    TIER_ENVIRONMENT,
    classify_text,
)
from swebench.harness.reporting import make_run_report

BROWSER_FAILURE = """
> karma start karma.conf.js
Failed to launch Chrome! Chromium revision is not downloaded.
"""

GENUINE_TEST_FAILURE = """
FAILED test_foo.py::test_bar - AssertionError: expected 3, got 4
1 failed, 12 passed in 1.20s
"""


def test_browser_launch_is_environment_tier():
    assert classify_text(BROWSER_FAILURE) == ("browser_launch_failed", TIER_ENVIRONMENT)


def test_missing_module_is_only_ambiguous():
    # A bad patch can also cause this, so it must not be reported as confirmed infra.
    reason, tier = classify_text("Error: Cannot find module 'ol/layer/Vector'")
    assert (reason, tier) == ("missing_module", TIER_AMBIGUOUS)


def test_genuine_test_failure_is_not_classified():
    assert classify_text(GENUINE_TEST_FAILURE) is None


def test_empty_log_is_not_classified():
    assert classify_text("") is None


def _write_run(
    monkeypatch, tmp_path, run_id, test_output, resolved=False, write_report=True
):
    """Lay out a one-instance run under tmp_path the way run_evaluation does.

    RUN_EVALUATION_LOG_DIR is CWD-relative, so it is redirected here to keep the
    tests from writing into a real run's log tree.
    """
    monkeypatch.setattr(reporting, "RUN_EVALUATION_LOG_DIR", tmp_path / "logs")
    instance_id = "openlayers__openlayers-10340"
    predictions = {
        instance_id: {
            "instance_id": instance_id,
            "model_name_or_path": "gold",
            "model_patch": "diff --git a b",
        }
    }
    log_dir = tmp_path / "logs" / run_id / "gold" / instance_id
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / LOG_TEST_OUTPUT).write_text(test_output)
    (log_dir / LOG_INSTANCE).write_text("run log")
    if write_report:
        (log_dir / LOG_REPORT).write_text(
            json.dumps({instance_id: {"resolved": resolved}})
        )
    return predictions, [{"instance_id": instance_id}], instance_id


def test_infra_failure_stays_in_the_denominator(monkeypatch, tmp_path):
    predictions, dataset, instance_id = _write_run(
        monkeypatch, tmp_path, "infra-denominator", BROWSER_FAILURE
    )
    out = make_run_report(predictions, dataset, "infra-denominator")
    report = json.loads(out.read_text())

    # Flagged as infra...
    assert report["infra_failure_ids"] == [instance_id]
    assert report["failure_reasons"][instance_id] == "browser_launch_failed"
    # ...but still counted as unresolved, so the denominator is unchanged.
    assert report["unresolved_ids"] == [instance_id]
    assert report["unresolved_instances"] == 1
    assert report["resolved_instances"] == 0
    assert report["completed_instances"] == 1


def test_resolved_instance_is_never_classified(monkeypatch, tmp_path):
    predictions, dataset, instance_id = _write_run(
        monkeypatch, tmp_path, "infra-resolved", BROWSER_FAILURE, resolved=True
    )
    out = make_run_report(predictions, dataset, "infra-resolved")
    report = json.loads(out.read_text())

    assert report["resolved_ids"] == [instance_id]
    assert report["infra_failure_ids"] == []
    assert report["failure_reasons"] == {}


def test_error_instances_without_a_report_are_classified(monkeypatch, tmp_path):
    predictions, dataset, instance_id = _write_run(
        monkeypatch, tmp_path, "infra-error", BROWSER_FAILURE, write_report=False
    )
    out = make_run_report(predictions, dataset, "infra-error")
    report = json.loads(out.read_text())

    assert report["error_ids"] == [instance_id]
    assert report["infra_failure_ids"] == [instance_id]


def test_genuine_failure_is_not_flagged(monkeypatch, tmp_path):
    predictions, dataset, instance_id = _write_run(
        monkeypatch, tmp_path, "infra-genuine", GENUINE_TEST_FAILURE
    )
    out = make_run_report(predictions, dataset, "infra-genuine")
    report = json.loads(out.read_text())

    assert report["unresolved_ids"] == [instance_id]
    assert report["infra_failure_ids"] == []
    assert report["ambiguous_failure_ids"] == []


def test_nested_empty_pytest_run_does_not_override_outer_results():
    text = (
        "collected 16 items\n"
        "collected 0 items\n"
        "================ no tests ran in 0.01s ================\n"
        "FAILED testing/logging/test_fixture.py::test_clear_for_call_stage\n"
        "================ 1 failed, 15 passed in 0.46s ================\n"
    )
    assert classify_text(text) is None


def test_genuine_empty_pytest_run_stays_ambiguous():
    text = (
        "collected 0 items\n================ no tests ran in 0.01s ================\n"
    )
    assert classify_text(text) == ("no_tests_collected", TIER_AMBIGUOUS)


def test_collection_error_is_not_hidden_by_an_earlier_nested_success():
    text = (
        "================ 1 passed in 0.01s ================\n"
        "collected 0 items / 1 error\n"
        "================ 1 error in 0.02s ================\n"
    )
    assert classify_text(text) == ("no_tests_collected", TIER_AMBIGUOUS)


def test_later_empty_suite_is_not_hidden_by_an_earlier_success():
    text = (
        "================ 2 passed in 0.01s ================\n"
        "collected 0 items\n"
        "================ no tests ran in 0.02s ================\n"
    )
    assert classify_text(text) == ("no_tests_collected", TIER_AMBIGUOUS)


def test_all_deselected_is_still_no_tests_collected():
    text = (
        "collected 0 items\n================ 16 deselected in 0.01s ================\n"
    )
    assert classify_text(text) == ("no_tests_collected", TIER_AMBIGUOUS)


def test_other_failure_signatures_keep_their_priority():
    text = (
        "ModuleNotFoundError: No module named appdirs\n"
        "collected 0 items\n"
        "================ 1 failed, 15 passed in 0.46s ================\n"
    )
    assert classify_text(text) == ("missing_module", TIER_AMBIGUOUS)


def test_timeout_is_not_hidden_by_a_nested_empty_run():
    text = (
        "collected 0 items\n"
        "================ 1 failed, 15 passed in 0.46s ================\n"
        "Timeout error: 1800 seconds exceeded\n"
    )
    assert classify_text(text) == ("tests_timed_out", TIER_AMBIGUOUS)
