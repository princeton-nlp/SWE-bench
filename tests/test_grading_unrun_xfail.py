"""A patch must not pass by marking the F2P test ``xfail(run=False)`` (#654).

XFAIL grades as a pass, and ``pytest.mark.xfail(run=False)`` reports XFAIL
without executing the test body. So a patch could mark the FAIL_TO_PASS test
``xfail(run=False)`` -- from a ``conftest.py`` already in the repo, which the
pre-test checkout leaves in place because it is not in the instance's
``test_patch`` -- and grade resolved with the bug untouched.

pytest distinguishes the two cases in the ``-rA`` short summary the harness
parses: an xfail whose body never ran carries a ``[NOTRUN]`` marker. An xfail
that did run must keep grading as a pass, which is what
scikit-learn__scikit-learn-15100 relies on (see test_grading_truncated_ids.py).

The same hole for SKIPPED is already closed in ``test_failed``.
"""

import subprocess
import sys
import textwrap

from swebench.harness.constants import TestStatus
from swebench.harness.grading import test_failed as grade_failed
from swebench.harness.grading import test_maintained as grade_maintained
from swebench.harness.grading import test_passed as grade_passed
from swebench.harness.log_parsers.python import (
    parse_log_pytest,
    parse_log_pytest_options,
)

F2P = "sklearn/utils/tests/test_show_versions.py::test_get_deps_info"
RAN = "tests/test_text.py::test_ran_xfail"

# pytest -rA short summary. The trailing space after [NOTRUN] is pytest's.
LOG = f"""PASSED sklearn/utils/tests/test_show_versions.py::test_get_deps_info_other
XFAIL {F2P} - [NOTRUN] 
XFAIL {RAN}
"""


def test_pytest_emits_notrun_only_for_unrun_xfail():
    """Pin the pytest behaviour the fix depends on, so an upgrade cannot silently
    remove the only signal that separates the two kinds of xfail."""
    source = textwrap.dedent("""
        import pytest

        @pytest.mark.xfail(run=False)
        def test_never_runs():
            raise AssertionError("body must not execute")

        @pytest.mark.xfail
        def test_does_run():
            raise AssertionError("body executes and fails as expected")
    """)
    import pathlib
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "test_xfail_shapes.py"
        path.write_text(source)
        out = subprocess.run(
            [sys.executable, "-m", "pytest", str(path), "-rA", "-p", "no:cacheprovider"],
            capture_output=True,
            text=True,
            cwd=tmp,
        ).stdout

    notrun = [ln for ln in out.splitlines() if ln.startswith("XFAIL") and "[NOTRUN]" in ln]
    ran = [ln for ln in out.splitlines() if ln.startswith("XFAIL") and "[NOTRUN]" not in ln]

    assert len(notrun) == 1, out
    assert "test_never_runs" in notrun[0], out
    assert len(ran) == 1, out
    assert "test_does_run" in ran[0], out


def test_unrun_xfail_does_not_grade_as_passed():
    """The core hole: an F2P test that never ran must not count as resolved."""
    for parser in (parse_log_pytest, parse_log_pytest_options):
        sm = parser(LOG, None)

        assert sm[F2P] == TestStatus.SKIPPED.value, parser.__name__
        assert not grade_passed(F2P, sm), parser.__name__
        assert grade_failed(F2P, sm), parser.__name__


def test_xfail_that_ran_still_grades_as_passed():
    """An xfail that executed keeps its meaning; only [NOTRUN] is demoted."""
    for parser in (parse_log_pytest, parse_log_pytest_options):
        sm = parser(LOG, None)

        assert sm[RAN] == TestStatus.XFAIL.value, parser.__name__
        assert grade_passed(RAN, sm), parser.__name__
        assert not grade_failed(RAN, sm), parser.__name__


def test_unrun_xfail_is_not_a_p2p_regression():
    """P2P semantics are unchanged: not running a test is not a regression."""
    sm = parse_log_pytest(LOG, None)

    assert grade_maintained(F2P, sm)


def test_notrun_in_a_test_name_is_not_demoted():
    """The marker is only meaningful in pytest's own suffix, not in a test id."""
    sm = parse_log_pytest("XFAIL tests/test_x.py::test_notrun_helper\n", None)

    assert sm["tests/test_x.py::test_notrun_helper"] == TestStatus.XFAIL.value
    assert grade_passed("tests/test_x.py::test_notrun_helper", sm)
