"""Container-bound eval artifacts must be written with Unix newlines (#652).

On Windows, Path.write_text() translates '\\n' to CRLF. copy_to_container then
copies those bytes unchanged into the Linux eval container, so eval.sh fails
under bash and patch.diff can fail git apply.
"""

from pathlib import Path
from unittest.mock import MagicMock

from swebench.harness import run_evaluation
from swebench.types import TestSpec as EvalTestSpec

INSTANCE_ID = "repo__repo-1"


def _spec() -> EvalTestSpec:
    return EvalTestSpec(
        instance_id=INSTANCE_ID,
        image="unused",
        eval_script_list=["pytest"],
        repo="repo/repo",
        version="1.0",
        FAIL_TO_PASS=["test_a"],
        PASS_TO_PASS=[],
    )


def _pred() -> dict:
    return {
        "instance_id": INSTANCE_ID,
        "model_name_or_path": "gold",
        "model_patch": "diff --git a/x b/x\n",
    }


def test_patch_and_eval_writes_use_unix_newlines(monkeypatch, tmp_path):
    recorded: dict[str, str | None] = {}
    real_write_text = Path.write_text

    def spy(self, data, *args, **kwargs):
        newline = kwargs["newline"] if "newline" in kwargs else None
        if "newline" not in kwargs and len(args) >= 3:
            newline = args[2]
        recorded[self.name] = newline
        return real_write_text(self, data, *args, **kwargs)

    ok = MagicMock(exit_code=0, output=b"ok")
    container = MagicMock()
    container.id = "cid"
    container.exec_run.return_value = ok

    monkeypatch.setattr(run_evaluation.Path, "write_text", spy)
    monkeypatch.setattr(run_evaluation, "RUN_EVALUATION_LOG_DIR", tmp_path)
    monkeypatch.setattr(
        run_evaluation, "create_container", lambda *args, **kwargs: container
    )
    monkeypatch.setattr(
        run_evaluation, "copy_to_container", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        run_evaluation,
        "exec_run_with_timeout",
        lambda *args, **kwargs: ("ok", False, 1.0),
    )
    monkeypatch.setattr(
        run_evaluation, "cleanup_container", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        run_evaluation,
        "get_eval_report",
        lambda **kwargs: {INSTANCE_ID: {"resolved": True}},
    )

    run_evaluation.run_instance(_spec(), _pred(), MagicMock(), "nl-652", timeout=1)

    observed = {
        "patch.diff": recorded.get("patch.diff"),
        "eval.sh": recorded.get("eval.sh"),
    }
    assert observed == {"patch.diff": "\n", "eval.sh": "\n"}
