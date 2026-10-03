"""`swebench eval` and `swebench report`."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

import typer

from swebench.cli._datasets import alias_help, resolve_dataset

DATASET_ARG = typer.Argument(
    ...,
    metavar="DATASET",
    help=f"Dataset alias, HuggingFace id, or local path. Aliases: {alias_help()}",
)


def eval_command(
    dataset: str = DATASET_ARG,
    gold: bool = typer.Option(False, "--gold", help="Evaluate the reference patches"),
    predictions: Optional[str] = typer.Option(
        None, "-p", "--predictions", help="Path to a predictions .json/.jsonl"
    ),
    run_id: str = typer.Option("run", "-r", "--run-id", help="Names the log directory"),
    instance_ids: Optional[list[str]] = typer.Option(
        None, "-i", "--instance", help="Limit to these instances (repeatable)"
    ),
    split: str = typer.Option("test", "-s", "--split"),
    workers: int = typer.Option(
        4, "-j", "--workers", help="Instances evaluated in parallel"
    ),
    timeout: int = typer.Option(1800, "-t", "--timeout", help="Per-instance seconds"),
    task_repo: Optional[str] = typer.Option(
        None,
        "--task-repo",
        help=(
            "Build images from this task repo instead of trusting the registry. "
            "Without it images are pulled, so a stale published image can mask a broken "
            "build; failed builds are reported and only fall back to a published image "
            "when one exists."
        ),
    ),
    modal: bool = typer.Option(
        False, "--modal", help="Run on Modal instead of local Docker"
    ),
    open_file_limit: int = typer.Option(4096, "--open-file-limit"),
):
    """Evaluate gold or model predictions against a dataset.

    [yellow][bold]Examples:[/bold][/yellow]

        swebench eval verified --gold

        swebench eval verified -p preds.jsonl --run-id gpt5 -j 16

        swebench eval multimodal --gold -i carbon-design-system__carbon-10188

        swebench eval full --gold --modal
    """
    if gold and predictions:
        raise typer.BadParameter("pass either --gold or --predictions, not both")
    if not gold and not predictions:
        raise typer.BadParameter("pass --gold or --predictions <path>")

    from swebench.harness.run_evaluation import main as run_evaluation

    run_evaluation(
        dataset_name=resolve_dataset(dataset),
        split=split,
        instance_ids=list(instance_ids) if instance_ids else None,
        predictions_path="gold" if gold else predictions,
        max_workers=workers,
        open_file_limit=open_file_limit,
        run_id=run_id,
        timeout=timeout,
        rewrite_reports=False,
        modal=modal,
        task_repo=task_repo,
    )


def report_command(
    run_id: str = typer.Argument(..., help="Run id to re-grade"),
    dataset: Optional[str] = typer.Option(
        None,
        "-d",
        "--dataset",
        help="Dataset the run used; taken from the run if omitted",
    ),
    split: Optional[str] = typer.Option(None, "-s", "--split"),
    instance_ids: Optional[list[str]] = typer.Option(None, "-i", "--instance"),
    model: Optional[str] = typer.Option(
        None,
        "-m",
        "--model",
        help="Model dir inside the run (auto-detected if only one)",
    ),
):
    """Re-grade a finished run from its saved logs, without starting containers.

    Useful after a log-parser fix: the test output is already on disk, so the
    verdicts can be recomputed in seconds.

    [yellow][bold]Examples:[/bold][/yellow]

        swebench report my-run -d verified

        swebench report my-run -d multimodal -i grommet__grommet-6282
    """
    from swebench.harness.run_evaluation import main as run_evaluation
    from swebench.harness.run_evaluation import read_run_metadata
    from swebench.harness.constants import RUN_EVALUATION_LOG_DIR
    from swebench.submit.package import PackageError, resolve_run_dir

    recorded = read_run_metadata(run_id) or {}
    if dataset is None:
        if not recorded.get("dataset"):
            typer.echo(
                f"Run {run_id!r} did not record which dataset it used, so pass -d. "
                "Runs made before this was added have no record of it.",
                err=True,
            )
            raise typer.Exit(1)
        dataset = recorded["dataset"]
    if split is None:
        split = recorded.get("split", "test")

    try:
        run = resolve_run_dir(RUN_EVALUATION_LOG_DIR / run_id, model)
    except PackageError as exc:
        raise typer.BadParameter(str(exc)) from exc

    predictions = []
    for artifacts in sorted(run.logs_dir.iterdir()):
        if not artifacts.is_dir() or (
            instance_ids and artifacts.name not in instance_ids
        ):
            continue
        patch = artifacts / "patch.diff"
        if not patch.is_file():
            # A missing prediction must not be replaced with the reference patch.
            if (artifacts / "test_output.txt").is_file():
                raise typer.BadParameter(f"Missing saved prediction: {patch}")
            continue
        predictions.append(
            {
                "instance_id": artifacts.name,
                "model_name_or_path": run.model,
                "model_patch": patch.read_text(),
            }
        )

    # Keep the harness's prediction-file API, using only the evaluated patches.
    # The temporary file lives until grading completes and is never an artifact.
    with TemporaryDirectory() as temp_dir:
        predictions_path = Path(temp_dir) / "predictions.json"
        predictions_path.write_text(json.dumps(predictions))
        run_evaluation(
            dataset_name=resolve_dataset(dataset),
            split=split,
            instance_ids=list(instance_ids) if instance_ids else None,
            predictions_path=str(predictions_path),
            max_workers=1,
            open_file_limit=4096,
            run_id=run_id,
            timeout=1800,
            rewrite_reports=True,
            modal=False,
            # Replay the same task repo's test definitions when one was recorded.
            task_repo=recorded.get("task_repo"),
        )
