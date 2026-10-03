"""The report CLI must replay a model's saved artifacts without Docker."""

import json
from pathlib import Path
import shutil
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from swebench.cli.cli import app
from swebench.harness import run_evaluation
from swebench.harness.constants import (
    END_TEST_OUTPUT,
    START_TEST_OUTPUT,
    TEST_EXIT_CODE,
)
from swebench.harness.grading import get_eval_report
from swebench.harness.utils import make_test_spec
from swebench.task.repo import dump_yaml


@pytest.fixture
def saved_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    instance = {
        "instance_id": "example__calculator-1",
        "repo": "example/calculator",
        "version": "1",
        "image": "unused/image:fixed",
        "eval_script": "echo unused",
        "log_parser": "parse_log_pytest",
        "eval_type": "pass_and_fail",
        "FAIL_TO_PASS": ["tests/test_calc.py::test_add"],
        "PASS_TO_PASS": ["tests/test_calc.py::test_zero"],
        "patch": "reference patch, different from the saved model patch",
    }
    dataset = tmp_path / "dataset.json"
    dataset.write_text(json.dumps([instance]))
    run_evaluation.write_run_metadata("replay", str(dataset), "test", None)
    root = tmp_path / "logs/evaluation/replay"

    def save(model="my-agent", status="PASSED", patch="saved model patch"):
        prediction = {
            "instance_id": instance["instance_id"],
            "model_name_or_path": model,
            "model_patch": patch,
        }
        artifacts = root / model.replace("/", "__") / instance["instance_id"]
        artifacts.mkdir(parents=True)
        (artifacts / "patch.diff").write_text(patch)
        log = artifacts / "test_output.txt"
        log.write_text(
            f"{START_TEST_OUTPUT}\n"
            f"{status} tests/test_calc.py::test_add\n"
            "PASSED tests/test_calc.py::test_zero\n"
            f"{END_TEST_OUTPUT}\n"
            f"{TEST_EXIT_CODE}: {0 if status == 'PASSED' else 1}\n"
        )
        original = get_eval_report(make_test_spec(instance), prediction, log, True)
        (artifacts / "report.json").write_text(json.dumps(original))
        return artifacts, original

    return root, save


@pytest.mark.parametrize("model", ["my-agent", "org/my-agent"])
@pytest.mark.parametrize("status", ["PASSED", "FAILED"])
def test_report_replays_the_saved_model(saved_run, monkeypatch, model, status):
    root, save = saved_run
    artifacts, original = save(model, status)
    # Isolate the provenance bug from the separate Docker-daemon dependency.
    docker_client = MagicMock()
    docker_client.images.list.return_value = []
    docker_client.containers.list.return_value = []
    monkeypatch.setattr(run_evaluation, "_docker_client", lambda: docker_client)

    result = CliRunner().invoke(app, ["report", "replay"])

    assert result.exit_code == 0, result.output
    summary = json.loads((root / "results.json").read_text())
    assert summary["completed_ids"] == ["example__calculator-1"]
    assert summary["resolved_instances"] == int(status == "PASSED")
    assert json.loads((artifacts / "report.json").read_text()) == original


def test_gold_replay_does_not_require_a_docker_daemon(saved_run, monkeypatch):
    root, save = saved_run
    save("gold")

    def no_docker():
        raise AssertionError("Saved-log replay must not connect to Docker")

    monkeypatch.setattr(run_evaluation, "_docker_client", no_docker)
    result = CliRunner().invoke(app, ["report", "replay"])

    assert result.exit_code == 0, repr(result.exception)
    assert json.loads((root / "results.json").read_text())["resolved_instances"] == 1


def test_replay_ignores_cached_verdicts_and_preserves_metadata(saved_run, monkeypatch):
    root, save = saved_run
    artifacts, original = save(status="FAILED")
    (artifacts / "report.json").write_text('{"untrusted": {"resolved": true}}')
    metadata = (root / "run.json").read_bytes()
    monkeypatch.setattr(run_evaluation, "_docker_client", lambda: pytest.fail("Docker"))

    result = CliRunner().invoke(app, ["report", "replay"])

    assert result.exit_code == 0, repr(result.exception)
    assert json.loads((artifacts / "report.json").read_text()) == original
    assert (root / "run.json").read_bytes() == metadata
    assert json.loads((root / "results.json").read_text())["resolved_instances"] == 0


def test_several_models_require_a_choice_before_writing(saved_run):
    root, save = saved_run
    save("gold")
    artifacts, _ = save("org/my-agent", status="FAILED")
    original = (artifacts / "report.json").read_bytes()

    result = CliRunner().invoke(app, ["report", "replay"])

    assert result.exit_code != 0
    assert "several models" in result.output
    assert (artifacts / "report.json").read_bytes() == original
    assert not (root / "results.json").exists()


def test_explicit_model_does_not_replay_gold(saved_run):
    root, save = saved_run
    gold_dir, _ = save("gold")
    model_dir, original = save("org/my-agent", status="FAILED")
    gold_report = (gold_dir / "report.json").read_bytes()

    result = CliRunner().invoke(app, ["report", "replay", "--model", "org/my-agent"])

    assert result.exit_code == 0, repr(result.exception)
    assert json.loads((model_dir / "report.json").read_text()) == original
    assert (gold_dir / "report.json").read_bytes() == gold_report
    assert json.loads((root / "results.json").read_text())["resolved_instances"] == 0


def test_missing_saved_patch_is_an_error_before_writing(saved_run):
    root, save = saved_run
    artifacts, _ = save()
    (artifacts / "patch.diff").unlink()
    original = (artifacts / "report.json").read_bytes()

    result = CliRunner().invoke(app, ["report", "replay"])

    assert result.exit_code != 0
    assert "Missing saved prediction" in result.output
    assert (artifacts / "report.json").read_bytes() == original
    assert not (root / "results.json").exists()


def test_empty_saved_prediction_is_not_scored_as_resolved(saved_run):
    root, save = saved_run
    save(patch="")

    result = CliRunner().invoke(app, ["report", "replay"])

    assert result.exit_code == 0, repr(result.exception)
    summary = json.loads((root / "results.json").read_text())
    assert summary["resolved_instances"] == 0
    assert summary["empty_patch_instances"] == 1


@pytest.mark.parametrize("log", ["truncated output", "", "malformed line 中文"])
def test_invalid_saved_output_is_not_a_resolution(saved_run, log):
    root, save = saved_run
    artifacts, _ = save()
    (artifacts / "test_output.txt").write_text(log)

    result = CliRunner().invoke(app, ["report", "replay"])

    assert result.exit_code == 0, repr(result.exception)
    summary = json.loads((root / "results.json").read_text())
    assert summary["resolved_instances"] == 0
    assert summary["unresolved_instances"] == 1


def test_older_run_can_supply_its_dataset(saved_run):
    root, save = saved_run
    save()
    dataset = json.loads((root / "run.json").read_text())["dataset"]
    (root / "run.json").unlink()

    result = CliRunner().invoke(app, ["report", "replay", "-d", dataset])

    assert result.exit_code == 0, repr(result.exception)
    assert json.loads((root / "results.json").read_text())["resolved_instances"] == 1
    assert not (root / "run.json").exists()


def test_replay_uses_saved_prediction_when_gold_is_absent(saved_run):
    root, save = saved_run
    save()
    dataset_path = json.loads((root / "run.json").read_text())["dataset"]
    instances = json.loads(Path(dataset_path).read_text())
    del instances[0]["patch"]
    with open(dataset_path, "w") as fh:
        json.dump(instances, fh)

    result = CliRunner().invoke(app, ["report", "replay"])

    assert result.exit_code == 0, repr(result.exception)
    assert json.loads((root / "results.json").read_text())["resolved_instances"] == 1


def test_missing_log_cannot_reuse_a_cached_resolution(saved_run):
    root, save = saved_run
    artifacts, _ = save()
    (artifacts / "test_output.txt").unlink()
    original_report = (artifacts / "report.json").read_bytes()
    (root / "results.json").write_text("previous summary")

    result = CliRunner().invoke(app, ["report", "replay"])

    assert result.exit_code != 0
    assert "Missing saved test output" in str(result.exception)
    assert (artifacts / "report.json").read_bytes() == original_report
    assert (root / "results.json").read_text() == "previous summary"


def test_attempt_with_no_log_or_report_keeps_its_error_classification(saved_run):
    root, save = saved_run
    artifacts, _ = save()
    (artifacts / "test_output.txt").unlink()
    (artifacts / "report.json").unlink()

    result = CliRunner().invoke(app, ["report", "replay"])

    assert result.exit_code == 0, repr(result.exception)
    summary = json.loads((root / "results.json").read_text())
    assert summary["resolved_instances"] == 0
    assert summary["error_ids"] == ["example__calculator-1"]


def test_parser_exception_aborts_before_aggregating_cached_reports(
    saved_run, monkeypatch
):
    root, save = saved_run
    artifacts, _ = save()
    original_report = (artifacts / "report.json").read_bytes()
    (root / "results.json").write_text("previous summary")

    def broken_parser(*args, **kwargs):
        raise ValueError("Cannot parse saved output")

    monkeypatch.setattr(run_evaluation, "get_eval_report", broken_parser)
    result = CliRunner().invoke(app, ["report", "replay"])

    assert result.exit_code != 0
    assert "Failed to re-grade: example__calculator-1" in str(result.exception)
    assert (artifacts / "report.json").read_bytes() == original_report
    assert (root / "results.json").read_text() == "previous summary"


@pytest.mark.parametrize("workers", [0, 1, 2, 4])
def test_legacy_replay_is_offline_and_independent_of_worker_count(
    saved_run, monkeypatch, workers
):
    root, save = saved_run
    artifacts, original = save(status="FAILED")
    metadata = json.loads((root / "run.json").read_text())
    predictions_path = root / "predictions.json"
    predictions_path.write_text(
        json.dumps(
            [
                {
                    "instance_id": "example__calculator-1",
                    "model_name_or_path": "my-agent",
                    "model_patch": (artifacts / "patch.diff").read_text(),
                }
            ]
        )
    )
    monkeypatch.setattr(run_evaluation, "_docker_client", lambda: pytest.fail("Docker"))

    run_evaluation.main(
        dataset_name=metadata["dataset"],
        split="test",
        instance_ids=None,
        predictions_path=str(predictions_path),
        max_workers=workers,
        open_file_limit=4096,
        run_id="replay",
        timeout=1,
        rewrite_reports=True,
        modal=False,
    )

    assert json.loads((artifacts / "report.json").read_text()) == original
    assert json.loads((root / "results.json").read_text())["resolved_instances"] == 0


def test_legacy_replay_rejects_a_report_without_a_log(saved_run):
    root, save = saved_run
    artifacts, _ = save("gold")
    (artifacts / "test_output.txt").unlink()
    metadata = json.loads((root / "run.json").read_text())

    with pytest.raises(ValueError, match="Missing saved test output"):
        run_evaluation.main(
            dataset_name=metadata["dataset"],
            split="test",
            instance_ids=None,
            predictions_path="gold",
            max_workers=1,
            open_file_limit=4096,
            run_id="replay",
            timeout=1,
            rewrite_reports=True,
            modal=False,
        )

    assert not (root / "results.json").exists()


def test_report_keeps_the_recorded_task_repo_as_its_test_source(saved_run):
    root, save = saved_run
    save()
    metadata = json.loads((root / "run.json").read_text())
    instance = json.loads(Path(metadata["dataset"]).read_text())[0]
    task_repo = root.parent / "task-repo"
    task_dir = task_repo / "tasks" / instance["instance_id"]
    task_dir.mkdir(parents=True)
    # The published dataset accepts the log, but this task repo requires another
    # F2P test. Replay must use the task definition the original run recorded.
    tests = {"FAIL_TO_PASS": ["tests/test_calc.py::test_other"], "PASS_TO_PASS": []}
    (task_dir / "tests.json").write_text(json.dumps(tests))
    (task_dir / "task.yaml").write_text(dump_yaml({**instance, "split": "test"}))
    for filename in ("gold.patch", "test.patch", "problem_statement.md", "eval.sh"):
        (task_dir / filename).write_text("unused")
    run_evaluation.write_run_metadata(
        "replay", metadata["dataset"], "test", str(task_repo)
    )
    recorded = (root / "run.json").read_bytes()

    result = CliRunner().invoke(app, ["report", "replay"])

    assert result.exit_code == 0, repr(result.exception)
    assert json.loads((root / "results.json").read_text())["resolved_instances"] == 0
    assert (root / "run.json").read_bytes() == recorded


def test_instance_filter_does_not_rewrite_other_saved_reports(saved_run):
    root, save = saved_run
    artifacts, _ = save()
    other = artifacts.parent / "example__calculator-2"
    shutil.copytree(artifacts, other)
    (other / "report.json").write_text("untouched")
    dataset_path = Path(json.loads((root / "run.json").read_text())["dataset"])
    instances = json.loads(dataset_path.read_text())
    instances.append({**instances[0], "instance_id": other.name})
    dataset_path.write_text(json.dumps(instances))

    result = CliRunner().invoke(app, ["report", "replay", "-i", artifacts.name])

    assert result.exit_code == 0, repr(result.exception)
    assert (other / "report.json").read_text() == "untouched"
    summary = json.loads((root / "results.json").read_text())
    assert summary["total_instances"] == 1
    assert summary["completed_ids"] == [artifacts.name]
