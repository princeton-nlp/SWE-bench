"""Infrastructure-failure classification must not touch the scoring denominator (#586).

The original approach in #594 routed infra failures out of both `resolved_ids` and
`unresolved_ids`, so any misclassified instance silently left the denominator and
inflated scores. These tests pin the additive behavior instead.
"""

import json
import os
import subprocess
import sys

import pytest

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


EMPTY_PYTEST = (
    "collected 0 items\n================ no tests ran in 0.01s ================\n"
)


@pytest.mark.parametrize(
    "outcome",
    ["1 failed, 15 passed", "16 passed", "16 skipped", "16 xfailed", "16 xpassed"],
)
def test_nested_empty_run_does_not_override_later_pytest_results(outcome):
    # #683: pytest's own tests can run an empty inner suite.
    text = f"collected 16 items\n{EMPTY_PYTEST}================ {outcome} in 0.46s ================\n"
    assert classify_text(text) is None


@pytest.mark.parametrize(
    "text",
    [
        EMPTY_PYTEST,
        "================ 2 passed in 0.01s ================\n" + EMPTY_PYTEST,
        "collected 0 items / 1 error\n================ 1 error in 0.02s ================\n",
        "collected 0 items\n================ 16 deselected in 0.01s ================\n",
        EMPTY_PYTEST + "collected 16 items\n",
        EMPTY_PYTEST + "================ 0 passed in 0.01s ================\n",
        EMPTY_PYTEST
        + "================ 1 passed in 0.01s ================\n"
        + "================ 1 error in 0.02s ================\n",
    ],
    ids=[
        "empty",
        "later-empty",
        "collection-error",
        "deselected",
        "unfinished",
        "zero-passed",
        "last-summary-error",
    ],
)
def test_no_decisive_later_pytest_summary_keeps_empty_suite_advisory(text):
    assert classify_text(text) == ("no_tests_collected", TIER_AMBIGUOUS)


@pytest.mark.parametrize(
    "diagnostic, expected",
    [
        ("Failed to launch Chrome!", ("browser_launch_failed", TIER_ENVIRONMENT)),
        (
            "ModuleNotFoundError: No module named appdirs",
            ("missing_module", TIER_AMBIGUOUS),
        ),
        ("Timeout error: 1800 seconds exceeded", ("tests_timed_out", TIER_AMBIGUOUS)),
    ],
)
def test_nested_empty_run_preserves_other_failure_signatures(diagnostic, expected):
    text = (
        EMPTY_PYTEST
        + "================ 1 failed, 15 passed in 0.46s ================\n"
    )
    assert classify_text(diagnostic + "\n" + text) == expected


def test_real_nested_pytest_report_keeps_failure_without_empty_suite_advisory(
    monkeypatch, tmp_path
):
    """Exercise real nested pytest output, then the saved-log report path.

    This is a local reproduction, not a replay of the issue reporter's task image.
    """
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "empty").mkdir()
    (suite / "test_outer.py").write_text(
        "import subprocess\n"
        "import sys\n\n"
        "def test_nested():\n"
        "    result = subprocess.run([sys.executable, '-m', 'pytest', '--color=no', 'empty'],\n"
        "                            capture_output=True, text=True, timeout=30)\n"
        "    print(result.stdout)\n"
        "    assert result.returncode == 5\n"
        "    assert False, 'intentional outer failure'\n\n"
        "def test_pass():\n"
        "    pass\n"
    )
    env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTEST_ADDOPTS": ""}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--color=no", "test_outer.py"],
        cwd=suite,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "collected 0 items" in result.stdout
    assert "no tests ran" in result.stdout
    assert "1 failed, 1 passed" in result.stdout
    assert classify_text(result.stdout) is None

    predictions, dataset, instance_id = _write_run(
        monkeypatch, tmp_path, "nested-pytest", result.stdout
    )
    report = json.loads(
        make_run_report(predictions, dataset, "nested-pytest").read_text()
    )
    assert report["failure_reasons"] == {}
    assert report["ambiguous_failure_ids"] == []
    assert report["infra_failure_ids"] == []
    assert report["unresolved_ids"] == [instance_id]
    assert report["completed_instances"] == report["total_instances"] == 1
    assert report["unresolved_instances"] == 1
    assert report["resolved_instances"] == 0
