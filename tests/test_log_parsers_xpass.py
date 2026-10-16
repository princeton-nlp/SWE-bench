"""Non-strict XPASS executes successfully and must not disappear from grading."""

import os
import subprocess
import sys

import pytest

from swebench.harness.constants import (
    END_TEST_OUTPUT,
    START_TEST_OUTPUT,
    TEST_EXIT_CODE,
)
from swebench.harness.grading import get_eval_report, get_logs_eval
from swebench.harness.log_parsers import PARSER_REGISTRY
from swebench.harness.log_parsers.python import parse_log_pytest_v2
from swebench.types import TestSpec as SweTestSpec

PARSERS = [
    "parse_log_pytest",
    "parse_log_pytest_options",
    "parse_log_pytest_v2",
    "parse_log_matplotlib",
]
FIXED_CASE = "test_case.py::test_fixed"
XPASS_CASE = "test_case.py::test_known_bug[XPASS]"


@pytest.fixture(scope="module")
def pytest_runs(tmp_path_factory):
    """Capture actual -rA output, including pytest's strict-XPASS failure form."""
    directory = tmp_path_factory.mktemp("xpass")
    (directory / "test_case.py").write_text(
        "import os\n"
        "import pytest\n"
        "FIXED = os.environ['CASE_FIXED'] == '1'\n"
        "def test_fixed():\n"
        "    assert FIXED\n"
        "@pytest.mark.parametrize('value', ['XPASS'])\n"
        "@pytest.mark.xfail(reason='an existing expected failure', "
        "strict=os.environ['CASE_STRICT'] == '1')\n"
        "def test_known_bug(value):\n"
        "    assert FIXED\n"
    )
    runs = {}
    for state, fixed, strict, expected_exit in [
        ("before", "0", "0", 1),
        ("after", "1", "0", 0),
        ("strict", "1", "1", 1),
    ]:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "test_case.py", "-rA", "--color=no"],
            cwd=directory,
            env={
                **os.environ,
                "CASE_FIXED": fixed,
                "CASE_STRICT": strict,
                "PYTEST_ADDOPTS": "",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            },
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        assert result.returncode == expected_exit, output
        runs[state] = (output, result.returncode)
    assert f"XFAIL {XPASS_CASE}" in runs["before"][0]
    assert f"XPASS {XPASS_CASE} - an existing expected failure" in runs["after"][0]
    assert f"FAILED {XPASS_CASE}" in runs["strict"][0]
    assert "[XPASS(strict)]" in runs["strict"][0]
    return runs


def _spec(parser, xpass_is_f2p=False):
    return SweTestSpec(
        instance_id="synthetic-xpass-1",
        image="unused",
        eval_script_list=[],
        repo="synthetic/reproduction",
        version="1",
        FAIL_TO_PASS=[XPASS_CASE] if xpass_is_f2p else [FIXED_CASE],
        PASS_TO_PASS=[] if xpass_is_f2p else [XPASS_CASE],
        log_parser=parser,
        eval_type="pass_and_fail",
    )


def _log(tmp_path, output, exit_code):
    path = tmp_path / "test_output.txt"
    path.write_text(
        f"{START_TEST_OUTPUT}\n{output}\n{END_TEST_OUTPUT}\n"
        f"{TEST_EXIT_CODE}: {exit_code}\n"
    )
    return str(path)


def _report(spec, path):
    prediction = {
        "instance_id": spec.instance_id,
        "model_name_or_path": "no-model-used",
        "model_patch": "nonempty placeholder for grader-only test",
    }
    return get_eval_report(spec, prediction, path, True)[spec.instance_id]


@pytest.mark.parametrize("parser", PARSERS)
def test_non_strict_xpass_is_preserved_as_passed(parser, pytest_runs):
    output, _ = pytest_runs["after"]
    assert PARSER_REGISTRY[parser](output, None) == {
        FIXED_CASE: "PASSED",
        XPASS_CASE: "PASSED",
    }


@pytest.mark.parametrize("parser", PARSERS)
@pytest.mark.parametrize("xpass_is_f2p", [False, True], ids=["p2p", "f2p"])
def test_non_strict_xpass_resolves(parser, xpass_is_f2p, pytest_runs, tmp_path):
    spec = _spec(parser, xpass_is_f2p)
    if not xpass_is_f2p:
        assert not _report(spec, _log(tmp_path, *pytest_runs["before"]))["resolved"]
    assert _report(spec, _log(tmp_path, *pytest_runs["after"]))["resolved"]


@pytest.mark.parametrize("parser", PARSERS)
def test_strict_xpass_remains_failed(parser, pytest_runs, tmp_path):
    spec = _spec(parser)
    path = _log(tmp_path, *pytest_runs["strict"])
    status_map, found = get_logs_eval(spec, path)
    assert found
    assert status_map[XPASS_CASE] == "FAILED"
    assert not _report(spec, path)["resolved"]


@pytest.mark.parametrize("parser", PARSERS)
def test_xpass_does_not_bypass_exit_code_guard(parser, pytest_runs, tmp_path):
    output, _ = pytest_runs["after"]
    path = _log(tmp_path, output, 1)
    assert get_logs_eval(_spec(parser), path) == ({}, False)
    assert not _report(_spec(parser), path)["resolved"]


@pytest.mark.parametrize("parameter", ["a b", "a - b", "[a - b]", "[", "]", "[a", "a]"])
def test_v2_xpass_preserves_spaces_in_parameter_id(parameter):
    output = f"XPASS test_case.py::test_known_bug[{parameter}] - expected - failure"
    assert parse_log_pytest_v2(output, None) == {
        f"test_case.py::test_known_bug[{parameter}]": "PASSED"
    }


def test_v2_legacy_trailing_xpass():
    assert parse_log_pytest_v2("test_case.py::test_known_bug[a b] XPASS", None) == {
        "test_case.py::test_known_bug[a b]": "PASSED"
    }


@pytest.mark.parametrize("status", ["PASSED", "FAILED", "SKIPPED", "ERROR", "XFAIL"])
def test_trailing_xpass_in_status_first_reason_is_unchanged(status):
    output = f"{status} test_case.py::test_bug - reason XPASS"
    # Existing v2 behavior strips FAILED reasons only. Normalization must not
    # rewrite any other status's reason or the resulting legacy map key.
    key = (
        "test_case.py::test_bug"
        if status == "FAILED"
        else "test_case.py::test_bug - reason XPASS"
    )
    assert parse_log_pytest_v2(output, None) == {key: status}


def test_xpass_reason_with_brackets_is_not_part_of_nonparametrized_id():
    output = "XPASS test_case.py::test_bug - expected [failure] - reason"
    assert parse_log_pytest_v2(output, None) == {"test_case.py::test_bug": "PASSED"}
