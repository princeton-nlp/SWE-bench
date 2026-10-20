from enum import Enum
from pathlib import Path
from typing import TypedDict


class ResolvedStatus(Enum):
    NO = "RESOLVED_NO"
    PARTIAL = "RESOLVED_PARTIAL"
    FULL = "RESOLVED_FULL"


class TestStatus(Enum):
    FAILED = "FAILED"
    PASSED = "PASSED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"
    XFAIL = "XFAIL"
    XPASS = "XPASS"


class EvalType(Enum):
    PASS_AND_FAIL = "pass_and_fail"
    FAIL_ONLY = "fail_only"


# Constants - Log Directories
INFERENCE_LOG_DIR = Path("logs/inference")
RUN_EVALUATION_LOG_DIR = Path("logs/evaluation")

# Constants - Test Types, Statuses, Commands
FAIL_TO_PASS = "FAIL_TO_PASS"
FAIL_TO_FAIL = "FAIL_TO_FAIL"
PASS_TO_PASS = "PASS_TO_PASS"
PASS_TO_FAIL = "PASS_TO_FAIL"

# Constants - Evaluation Execution
CONTAINER_PATCH_FILE = "/tmp/patch.diff"
LOG_REPORT = "report.json"
# what a run was: written at eval time so `swebench report` can re-grade it later
LOG_RUN_METADATA = "run.json"
LOG_INSTANCE = "run_instance.log"
LOG_TEST_OUTPUT = "test_output.txt"

# Constants - Evaluation Logging
APPLY_PATCH_FAIL = ">>>>> Patch Apply Failed"
APPLY_PATCH_PASS = ">>>>> Applied Patch"
RESET_FAILED = ">>>>> Reset Failed"
TESTS_ERROR = ">>>>> Tests Errored"
TESTS_FAILED = ">>>>> Some Tests Failed"
TESTS_PASSED = ">>>>> All Tests Passed"
TESTS_TIMEOUT = ">>>>> Tests Timed Out"
START_TEST_OUTPUT = ">>>>> Start Test Output"
END_TEST_OUTPUT = ">>>>> End Test Output"
TEST_EXIT_CODE = ">>>>> Test Exit Code"
# shell variable the eval script stashes the test command's $? in
TEST_EXIT_CODE_VAR = "SWEBENCH_TEST_EXIT_CODE"

# Constants - Evaluation Miscellaneous
NON_TEST_EXTS = [
    ".json",
    ".png",
    "csv",
    ".txt",
    ".md",
    ".jpg",
    ".jpeg",
    ".pkl",
    ".yml",
    ".yaml",
    ".toml",
]
SWE_BENCH_URL_RAW = "https://raw.githubusercontent.com/"
FAIL_ONLY_REPOS = {
    "chartjs/Chart.js",
    "processing/p5.js",
    "markedjs/marked",
    "bpmn-io/bpmn-js",
    "openlayers/openlayers",
    # eslint's log parser (parse_log_eslint) only records failing tests from
    # the `--reporter min` output, so it must be graded fail-only; otherwise
    # every gold eslint instance is (incorrectly) marked unresolved.
    "eslint/eslint",
}
