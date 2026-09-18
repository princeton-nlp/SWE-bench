"""A run records what it graded against (#report).

Re-grading needs the expected tests and the log parser, which live in the dataset
rather than in the run's logs. Without a record, `swebench report` has to be told
the dataset again, and grades against the wrong one silently if told wrongly.
"""

import json
import time
from unittest.mock import MagicMock

import pytest

from swebench.harness import run_evaluation


@pytest.fixture
def run_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(run_evaluation, "RUN_EVALUATION_LOG_DIR", tmp_path)
    return tmp_path


def test_metadata_round_trips(run_dir):
    run_evaluation.write_run_metadata(
        "my-run", "SWE-bench/SWE-bench_Verified", "test", None
    )
    got = run_evaluation.read_run_metadata("my-run")
    assert got["dataset"] == "SWE-bench/SWE-bench_Verified"
    assert got["split"] == "test"
    assert got["allow_network"] is False
    assert got["network_mode"] == "none"
    assert got["offline_deps_dir"] is None
    assert got["prediction_mode"] == "gold"
    assert got["created_at"]


def test_the_task_repo_is_recorded_when_one_was_used(run_dir):
    run_evaluation.write_run_metadata("my-run", "org/ds", "dev", "/path/to/tasks")
    assert run_evaluation.read_run_metadata("my-run")["task_repo"] == "/path/to/tasks"


def test_a_run_without_metadata_reads_as_none(run_dir):
    (run_dir / "old-run").mkdir()
    assert run_evaluation.read_run_metadata("old-run") is None


def test_metadata_is_written_beside_the_instance_logs(run_dir):
    path = run_evaluation.write_run_metadata("my-run", "org/ds", "test", None)
    assert path == run_dir / "my-run" / "run.json"
    assert json.loads(path.read_text())["dataset"] == "org/ds"


def test_network_opt_in_and_private_bundle_are_recorded(run_dir, tmp_path):
    run_evaluation.write_run_metadata(
        "my-run",
        "org/ds",
        "test",
        None,
        allow_network=True,
        offline_deps_dir=tmp_path,
    )

    got = run_evaluation.read_run_metadata("my-run")
    assert got["allow_network"] is True
    assert got["network_mode"] == "default"
    assert got["offline_deps_dir"] == str(tmp_path.resolve())


def test_network_override_is_recorded(run_dir, monkeypatch):
    monkeypatch.setenv("SWEBENCH_NETWORK_MODE", "host")
    run_evaluation.write_run_metadata(
        "my-run", "org/ds", "test", None, allow_network=True
    )

    assert run_evaluation.read_run_metadata("my-run")["network_mode"] == "host"


def test_compatible_resume_keeps_original_metadata_timestamp(run_dir):
    path = run_evaluation.write_run_metadata(
        "my-run", "org/ds", "test", None, allow_network=True
    )
    original = path.read_text()
    time.sleep(0.01)

    run_evaluation.write_run_metadata(
        "my-run", "org/ds", "test", None, allow_network=True
    )

    assert path.read_text() == original


def test_incompatible_resume_cannot_relabel_network_mode(run_dir):
    run_evaluation.write_run_metadata(
        "my-run", "org/ds", "test", None, allow_network=True
    )

    with pytest.raises(ValueError, match="incompatible execution metadata"):
        run_evaluation.write_run_metadata(
            "my-run", "org/ds", "test", None, allow_network=False
        )


def test_regrading_does_not_rewrite_historical_execution_metadata(run_dir, monkeypatch):
    """Old runs had network access, so absence must not be rewritten as `none`."""
    path = run_dir / "old-run" / "run.json"
    path.parent.mkdir()
    original = {"dataset": "org/ds", "split": "test"}
    path.write_text(json.dumps(original))

    monkeypatch.setattr(run_evaluation, "get_predictions_from_file", lambda *a: [])
    monkeypatch.setattr(run_evaluation, "get_dataset_from_preds", lambda *a, **k: [])
    monkeypatch.setattr(run_evaluation, "load_instances", lambda *a, **k: [])
    monkeypatch.setattr(run_evaluation.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(run_evaluation, "_docker_client", MagicMock())
    monkeypatch.setattr(run_evaluation, "make_run_report", MagicMock())

    run_evaluation.main(
        dataset_name="org/ds",
        split="test",
        instance_ids=[],
        predictions_path="gold",
        max_workers=1,
        open_file_limit=4096,
        run_id="old-run",
        timeout=30,
        rewrite_reports=True,
        modal=False,
    )

    assert json.loads(path.read_text()) == original
