import logging
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from swebench.harness.constants import CONTAINER_PATCH_FILE
from swebench.harness.run_evaluation import CONTAINER_ENV_DIFF_FILE, _apply_model_patch

pytestmark = pytest.mark.skipif(
    not (shutil.which("git") and shutil.which("patch")),
    reason="needs git and patch",
)

LOGGER = logging.getLogger(__name__)


class LocalContainer:
    """Runs exec_run commands in a local repo, with container paths mapped into tmp."""

    def __init__(self, repo, tmp):
        self.repo = repo
        self.paths = {
            CONTAINER_PATCH_FILE: str(tmp / "patch.diff"),
            CONTAINER_ENV_DIFF_FILE: str(tmp / "env.diff"),
        }

    def exec_run(self, cmd, workdir=None, user=None):
        if isinstance(cmd, str):
            cmd = ["/bin/bash", "-c", cmd]
        script = cmd[-1]
        for container_path, local_path in self.paths.items():
            script = script.replace(container_path, local_path)
        proc = subprocess.run([*cmd[:-1], script], cwd=self.repo, capture_output=True)
        return SimpleNamespace(
            exit_code=proc.returncode, output=proc.stdout + proc.stderr
        )


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def numbered(n, edits=None):
    lines = [f"line {i}" for i in range(1, n + 1)]
    for i, text in (edits or {}).items():
        lines[i - 1] = text
    return "\n".join(lines) + "\n"


def drifted(tmp_path, drift):
    """A repo whose HEAD drifted from the base a patch was written against.

    The patch changes lines 5 and 30; `drift` then edits HEAD inside the second
    hunk's context, so plain `git apply` fails and the fallbacks have to run.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "test")
    src = repo / "f.txt"
    src.write_text(numbered(40))
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    src.write_text(numbered(40, {5: "line 5 CHANGED", 30: "line 30 CHANGED"}))
    patch = subprocess.run(
        ["git", "diff"], cwd=repo, check=True, capture_output=True
    ).stdout
    (tmp_path / "patch.diff").write_bytes(patch)
    src.write_text(numbered(40, drift))
    git(repo, "commit", "-qam", "drift")
    return repo, tmp_path


def test_fuzz_fallback_applies_after_3way_conflict(tmp_path):
    # drift next to the changed line: --3way (the preimage blob is in history)
    # leaves a conflict, and only `patch --fuzz` applies it
    repo, tmp = drifted(tmp_path, {29: "line 29 drifted", 31: "line 31 drifted"})

    applied, _ = _apply_model_patch(LocalContainer(repo, tmp), LOGGER)

    assert applied
    text = (repo / "f.txt").read_text()
    assert "<<<<<<<" not in text
    assert text == numbered(
        40,
        {
            5: "line 5 CHANGED",
            29: "line 29 drifted",
            30: "line 30 CHANGED",
            31: "line 31 drifted",
        },
    )


def test_uncommitted_setup_edit_survives_retries(tmp_path):
    # drift two lines away from the change: --3way merges it cleanly
    repo, tmp = drifted(tmp_path, {33: "line 33 drifted"})
    # what a task Dockerfile's `sed -i` leaves behind without committing it
    (repo / "build.cfg").write_text("showPassed = false\n")
    git(repo, "add", "build.cfg")
    git(repo, "commit", "-qm", "config")
    (repo / "build.cfg").write_text("showPassed = true\n")

    applied, _ = _apply_model_patch(LocalContainer(repo, tmp), LOGGER)

    assert applied
    assert (repo / "build.cfg").read_text() == "showPassed = true\n"
    assert "line 30 CHANGED" in (repo / "f.txt").read_text()
