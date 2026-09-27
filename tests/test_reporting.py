"""Where make_run_report writes its results.json.

Always the run's own log directory. It used to land relative to the CWD, which meant a
run report appeared wherever the command happened to be invoked from (#498).
"""

import json

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


def test_submitted_counts_only_the_selected_instances(log_dir):
    """--instance_ids restricts full_dataset but not the predictions file (#666).

    The console line already intersected the two; the JSON did not, so a predictions file
    wider than the selection reported submitted_instances > total_instances.
    """
    selected = ["x__x-1", "x__x-2"]
    predictions = {
        instance_id: {
            "instance_id": instance_id,
            "model_name_or_path": "gold",
            "model_patch": "diff",
        }
        for instance_id in [*selected, "x__x-3", "x__x-4"]
    }
    full_dataset = [{"instance_id": instance_id} for instance_id in selected]

    out = make_run_report(predictions, full_dataset, "run-submitted")
    report = json.loads(out.read_text())

    assert report["submitted_instances"] == 2
    assert report["submitted_ids"] == selected
    assert report["submitted_instances"] <= report["total_instances"]


def test_submitted_is_every_prediction_when_nothing_is_filtered(log_dir):
    predictions, full_dataset = _fixture()
    out = make_run_report(predictions, full_dataset, "run-unfiltered")
    report = json.loads(out.read_text())
    assert report["submitted_ids"] == ["x__x-1"]
    assert report["submitted_instances"] == report["total_instances"] == 1
