"""Parametrized node IDs must retain significant whitespace when grading."""

import os
import subprocess
import sys

import pytest

from swebench.harness.constants import FAIL_TO_PASS, PASS_TO_PASS
from swebench.harness.grading import get_eval_tests_report
from swebench.harness.log_parsers.python import parse_log_pytest_v2


@pytest.mark.parametrize("status", ["PASSED", "FAILED", "SKIPPED", "ERROR", "XFAIL"])
@pytest.mark.parametrize("status_first", [True, False], ids=["summary", "legacy"])
def test_significant_whitespace_in_node_id_is_preserved(status, status_first):
    node_id = "tests/test_case.py::test_value[a  b]"
    line = f"{status} {node_id}" if status_first else f"{node_id} {status}"
    assert parse_log_pytest_v2(line, None) == {node_id: status}


def test_failed_summary_preserves_whitespace_but_excludes_assertion_message():
    node_id = "tests/test_case.py::test_value[a  b]"
    assert parse_log_pytest_v2(
        f"FAILED {node_id} - AssertionError: expected 1", None
    ) == {node_id: "FAILED"}


@pytest.mark.parametrize(
    "node_id",
    ["tests/test_case.py::test_value", "tests/test_case.py::test_value[a  b]"],
)
@pytest.mark.parametrize("status_first", [True, False], ids=["summary", "legacy"])
def test_outer_padding_is_not_part_of_the_node_id(node_id, status_first):
    line = f"PASSED {node_id}   " if status_first else f"   {node_id} PASSED"
    assert parse_log_pytest_v2(line, None) == {node_id: "PASSED"}


@pytest.fixture(scope="module")
def whitespace_pytest_output(tmp_path_factory):
    directory = tmp_path_factory.mktemp("pytest-whitespace")
    (directory / "test_case.py").write_text(
        "import pytest\n"
        "@pytest.mark.parametrize('value', [True, False], ids=['a b', 'a  b'])\n"
        "def test_value(value):\n"
        "    assert value\n"
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "test_case.py", "-rA", "--color=no"],
        cwd=directory,
        env={
            **os.environ,
            "PYTEST_ADDOPTS": "",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "PASSED test_case.py::test_value[a b]" in output
    assert "FAILED test_case.py::test_value[a  b]" in output
    return output


def test_real_pytest_results_keep_distinct_node_ids(whitespace_pytest_output):
    assert parse_log_pytest_v2(whitespace_pytest_output, None) == {
        "test_case.py::test_value[a b]": "PASSED",
        "test_case.py::test_value[a  b]": "FAILED",
    }


def test_real_pytest_results_are_matched_to_the_correct_gold_ids(
    whitespace_pytest_output,
):
    passing = "test_case.py::test_value[a b]"
    failing = "test_case.py::test_value[a  b]"
    report = get_eval_tests_report(
        parse_log_pytest_v2(whitespace_pytest_output, None),
        {FAIL_TO_PASS: [passing], PASS_TO_PASS: [failing]},
    )
    assert report[FAIL_TO_PASS] == {"success": [passing], "failure": []}
    assert report[PASS_TO_PASS] == {"success": [], "failure": [failing]}
