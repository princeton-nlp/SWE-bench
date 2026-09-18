"""Where make_run_report writes its results.json.

Always the run's own log directory. It used to land relative to the CWD, which meant a
run report appeared wherever the command happened to be invoked from (#498).
"""

import json
from unittest.mock import MagicMock

import docker
import pytest

from swebench.harness import reporting
from swebench.harness.reporting import make_run_report


def _fixture():
    predictions = {
        "x__x-1": {
            "instance_id": "x__x-1",
            "model_name_or_path": "gold",
            "model_patch": "diff",
        }
    }
    full_dataset = [{"instance_id": "x__x-1"}]
    return predictions, full_dataset


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    """RUN_EVALUATION_LOG_DIR is CWD-relative; point it somewhere disposable."""
    root = tmp_path / "logs" / "evaluation"
    monkeypatch.setattr(reporting, "RUN_EVALUATION_LOG_DIR", root)
    return root


def test_report_is_named_results_json(log_dir):
    predictions, full_dataset = _fixture()
    out = make_run_report(predictions, full_dataset, "run-a")
    assert out == log_dir / "run-a" / "results.json"
    assert out.exists()


def test_the_log_directory_is_created_if_absent(log_dir):
    predictions, full_dataset = _fixture()
    assert not log_dir.exists()
    out = make_run_report(predictions, full_dataset, "run-b")
    assert out.exists()


def test_defaults_into_the_runs_log_directory(log_dir):
    predictions, full_dataset = _fixture()
    out = make_run_report(predictions, full_dataset, "run-c")
    assert out == log_dir / "run-c" / "results.json"
    assert out.exists()


def test_two_runs_do_not_collide(log_dir):
    predictions, full_dataset = _fixture()
    a = make_run_report(predictions, full_dataset, "run-a")
    b = make_run_report(predictions, full_dataset, "run-b")
    assert a != b and a.exists() and b.exists()


def test_default_does_not_write_into_the_cwd(log_dir, tmp_path, monkeypatch):
    # the old default dropped gold.<run_id>.json wherever the command was invoked
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    predictions, full_dataset = _fixture()
    make_run_report(predictions, full_dataset, "run-d")
    assert list(cwd.iterdir()) == []


def test_daemon_cleanup_inspection_failure_does_not_lose_report(log_dir, monkeypatch):
    predictions, full_dataset = _fixture()
    client = MagicMock()
    monkeypatch.setattr(
        reporting,
        "list_images",
        MagicMock(side_effect=docker.errors.APIError("transient image-list failure")),
    )
    client.containers.list.side_effect = docker.errors.APIError(
        "transient container-list failure"
    )

    out = make_run_report(predictions, full_dataset, "run-e", client)

    assert json.loads(out.read_text())["total_instances"] == 1


def test_no_patch_run_is_completed_and_counted_as_empty(log_dir):
    instance_id = "x__x-1"
    predictions = {
        instance_id: {
            "instance_id": instance_id,
            "model_name_or_path": "no_patch",
            "model_patch": "__SWEBENCH_NO_PATCH__",
            "skip_patch": True,
        }
    }
    report_dir = log_dir / "baseline" / "no_patch" / instance_id
    report_dir.mkdir(parents=True)
    (report_dir / "report.json").write_text(
        json.dumps({instance_id: {"resolved": False}})
    )

    out = make_run_report(predictions, [{"instance_id": instance_id}], "baseline")
    summary = json.loads(out.read_text())

    assert summary["completed_instances"] == 1
    assert summary["unresolved_instances"] == 1
    assert summary["empty_patch_instances"] == 1
