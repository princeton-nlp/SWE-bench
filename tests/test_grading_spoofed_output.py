"""A patch must not be able to pass by printing its own PASSED lines (#620).

The eval script records the test command's exit status, and grading refuses to
score a log that claims no failures while the tests exited non-zero.

The status to record is the *test command's*, not the eval script's: scripts end
with a `git checkout` that resets the test files and run without `set -e`, so the
script's own status is the reset's. Getting that wrong both misses the spoof (the
reset usually succeeds, hiding a failing test run) and rejects genuine all-pass
runs whose reset fails, which is the case for every test patch that creates a new
test file.
"""

import inspect
import re
import subprocess
import sys

from swebench.harness.constants import END_TEST_OUTPUT, START_TEST_OUTPUT
from swebench.harness.grading import get_logs_eval, parse_test_exit_code
from swebench.harness.log_parsers import PARSER_REGISTRY
from swebench.harness.utils import record_test_exit_code
from swebench.types import TestSpec

RESET_CMD = "git checkout abc123 tests/test_new.py"
# in a real eval script the markers are no-op `:` commands, not bare text
START_LINE = f": '{START_TEST_OUTPUT}'"
END_LINE = f": '{END_TEST_OUTPUT}'"


def _spec():
    return TestSpec(
        instance_id="x__x-1",
        image="img",
        eval_script_list=[],
        repo="x/x",
        version="1.0",
        FAIL_TO_PASS=["test_a"],
        PASS_TO_PASS=[],
        log_parser="parse_log_pytest",
        eval_type="pass_and_fail",
    )


def _log(tmp_path, body, exit_code=None):
    parts = [START_TEST_OUTPUT, body, END_TEST_OUTPUT]
    if exit_code is not None:
        parts.append(f">>>>> Test Exit Code: {exit_code}")
    parts.append(RESET_CMD)
    log = tmp_path / "test_output.txt"
    log.write_text("\n".join(parts))
    return str(log)


def test_forged_passed_lines_are_not_graded(tmp_path):
    # Tests exited non-zero, yet the log reports nothing but passes.
    status_map, found = get_logs_eval(
        _spec(), _log(tmp_path, "PASSED test_a", exit_code=1)
    )
    assert (status_map, found) == ({}, False)


def test_forged_exit_code_inside_the_region_is_not_graded(tmp_path):
    # The patch forges a pass and also prints "Test Exit Code: 0"; the real one is 1.
    status_map, found = get_logs_eval(
        _spec(),
        _log(
            tmp_path,
            "PASSED test_a\n>>>>> Test Exit Code: 0",
            exit_code=1,
        ),
    )
    assert (status_map, found) == ({}, False)


def test_forged_end_marker_and_exit_code_are_not_graded(tmp_path):
    # The patch closes the region itself, forges an exit code, and the real failing
    # run follows; the first markers alone would score the forged pair.
    body = f"PASSED test_a\n{END_TEST_OUTPUT}\n>>>>> Test Exit Code: 0\nFAILED test_a"
    status_map, found = get_logs_eval(_spec(), _log(tmp_path, body, exit_code=1))
    assert (status_map, found) == ({}, False)


def test_set_x_trace_of_the_marker_is_not_a_conflict(tmp_path):
    # Under `set -x` the trace line repeats the same recorded value.
    log = tmp_path / "test_output.txt"
    log.write_text(
        f"{START_TEST_OUTPUT}\n"
        "PASSED test_a\n"
        f"{END_TEST_OUTPUT}\n"
        "+ echo '>>>>> Test Exit Code: 0'\n"
        ">>>>> Test Exit Code: 0\n"
        f"{RESET_CMD}\n"
    )
    status_map, found = get_logs_eval(_spec(), str(log))
    assert found and status_map == {"test_a": "PASSED"}


def test_a_repeated_marker_with_the_same_value_is_graded(tmp_path):
    status_map, found = get_logs_eval(
        _spec(),
        _log(tmp_path, "FAILED test_a\n>>>>> Test Exit Code: 1", exit_code=1),
    )
    assert found and status_map == {"test_a": "FAILED"}


def test_genuine_pass_is_graded(tmp_path):
    status_map, found = get_logs_eval(
        _spec(), _log(tmp_path, "PASSED test_a", exit_code=0)
    )
    assert found and status_map == {"test_a": "PASSED"}


def test_genuine_failure_is_graded(tmp_path):
    # Non-zero exit backed by a real FAILED line is an ordinary failing run.
    status_map, found = get_logs_eval(
        _spec(), _log(tmp_path, "FAILED test_a", exit_code=1)
    )
    assert found and status_map == {"test_a": "FAILED"}


def test_logs_without_a_recorded_exit_code_are_unaffected(tmp_path):
    # Runs predating this change, and script shapes with no end marker.
    status_map, found = get_logs_eval(_spec(), _log(tmp_path, "PASSED test_a"))
    assert found and status_map == {"test_a": "PASSED"}


def test_failing_reset_does_not_reject_a_passing_run(tmp_path):
    """The 18-instance regression: new-file test patches fail the trailing reset.

    The script exits non-zero because of the reset, but the recorded test status
    is 0, so the run must still be graded.
    """
    log = tmp_path / "test_output.txt"
    log.write_text(
        f"{START_TEST_OUTPUT}\n"
        "PASSED test_a\n"
        f"{END_TEST_OUTPUT}\n"
        ">>>>> Test Exit Code: 0\n"
        f"{RESET_CMD}\n"
        "error: pathspec 'tests/test_new.py' did not match any file(s) known to git\n"
    )
    status_map, found = get_logs_eval(_spec(), str(log))
    assert found and status_map == {"test_a": "PASSED"}


def test_exit_code_is_recorded_after_the_test_command(tmp_path):
    script = record_test_exit_code(
        [START_LINE, "pytest -rA tests/test_a.py", END_LINE, RESET_CMD]
    )
    capture = script.index("SWEBENCH_TEST_EXIT_CODE=$?")
    # Immediately after the test command, before anything can overwrite $?...
    assert script[capture - 1] == "pytest -rA tests/test_a.py"
    # ...and reported outside the parsed region, so log parsers never see it.
    assert script.index(END_LINE) == capture + 1
    assert script[capture + 2].startswith('echo ">>>>> Test Exit Code:')
    assert script[-1] == RESET_CMD


def _parser_source(fn, seen=None):
    """Source of a parser plus any parse_log_* helper it delegates to."""
    seen = seen if seen is not None else set()
    if fn.__name__ in seen:
        return ""
    seen.add(fn.__name__)
    source = inspect.getsource(fn)
    module = sys.modules[fn.__module__]
    for name in re.findall(r"\b(parse_log_\w+)\s*\(", source):
        helper = getattr(module, name, None)
        if callable(helper) and helper.__name__ != fn.__name__:
            source += _parser_source(helper, seen)
    return source


def test_every_parser_can_record_a_failure():
    """The check reads "recorded no failure" as evidence the log is not truthful.

    That only holds for parsers that could have recorded one. A parser that only
    ever records passes would make the condition true for its genuine failures
    too, and they would be thrown out instead of graded. None exist today; this
    fails if one is added, since the check would then need to exempt it.
    """
    assignable = re.compile(r"TestStatus\.(FAILED|ERROR)\b")
    blind = [
        name
        for name, parser in PARSER_REGISTRY.items()
        if not assignable.search(_parser_source(parser))
    ]
    assert blind == []


def test_scripts_without_an_end_marker_are_left_alone():
    script = ["make test", "echo done"]
    assert record_test_exit_code(script) == script


def test_parse_test_exit_code():
    assert parse_test_exit_code(">>>>> Test Exit Code: 0") == 0
    assert parse_test_exit_code(">>>>> Test Exit Code: 137") == 137
    assert parse_test_exit_code("no marker here") is None


def test_recorded_status_is_the_tests_not_the_scripts(tmp_path):
    """Run the generated script: the two statuses genuinely disagree.

    The trailing reset succeeds, so the script exits 0 and hides the failing test
    run. Only the recorded status still carries it.
    """
    script = record_test_exit_code(
        [
            START_LINE,
            "bash -c 'echo PASSED test_a; exit 1'",
            END_LINE,
            "true",  # stands in for a trailing reset that succeeds
        ]
    )
    path = tmp_path / "eval.sh"
    path.write_text("\n".join(["#!/bin/bash", "set -uxo pipefail", *script]))

    proc = subprocess.run(
        ["bash", str(path)], capture_output=True, text=True, check=False
    )

    assert proc.returncode == 0
    assert parse_test_exit_code(proc.stdout + proc.stderr) == 1
