"""`swebench eval` and `swebench report`."""

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
    no_patch: bool = typer.Option(
        False, "--no-patch", help="Evaluate pristine repositories as a negative control"
    ),
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
            "Without it images are pulled. With it, any failed or missing local build "
            "is fatal rather than falling back to a stale published image."
        ),
    ),
    reuse_images: bool = typer.Option(
        False,
        "--reuse-images",
        help=(
            "With --task-repo, use already-built local image tags instead of "
            "rebuilding them. Intended for a second pass over a verified build."
        ),
    ),
    modal: bool = typer.Option(
        False, "--modal", help="Run on Modal instead of local Docker"
    ),
    allow_network: bool = typer.Option(
        False,
        "--allow-network",
        help=(
            "Allow network access in local evaluation containers. By default, "
            "graders run with Docker network mode 'none'."
        ),
    ),
    offline_deps_dir: Optional[str] = typer.Option(
        None,
        "--offline-deps-dir",
        help=(
            "Private grader cache root. Its <instance_id> child is mounted "
            "as an immutable seed for /run/swebench-offline."
        ),
    ),
    open_file_limit: int = typer.Option(4096, "--open-file-limit"),
):
    """Evaluate gold or model predictions against a dataset.

    [yellow][bold]Examples:[/bold][/yellow]

        swebench eval verified --gold

        swebench eval verified -p preds.jsonl --run-id gpt5 -j 16

        swebench eval multimodal --gold --task-repo ./multimodal-tasks \
            -i carbon-design-system__carbon-10188

        swebench eval full --gold --modal
    """
    if sum((gold, no_patch, predictions is not None)) != 1:
        raise typer.BadParameter(
            "pass exactly one of --gold, --no-patch, or --predictions <path>"
        )

    from swebench.harness.run_evaluation import main as run_evaluation

    run_evaluation(
        dataset_name=resolve_dataset(dataset),
        split=split,
        instance_ids=list(instance_ids) if instance_ids else None,
        predictions_path="gold" if gold else "no-patch" if no_patch else predictions,
        max_workers=workers,
        open_file_limit=open_file_limit,
        run_id=run_id,
        timeout=timeout,
        rewrite_reports=False,
        modal=modal,
        task_repo=task_repo,
        reuse_images=reuse_images,
        allow_network=allow_network,
        offline_deps_dir=offline_deps_dir,
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
    prediction_mode = recorded.get("prediction_mode")
    if prediction_mode is None:
        from swebench.harness.constants import RUN_EVALUATION_LOG_DIR

        run_dir = RUN_EVALUATION_LOG_DIR / run_id
        prediction_mode = (
            "no-patch"
            if (run_dir / "no_patch").is_dir() and not (run_dir / "gold").is_dir()
            else "gold"
        )
    if prediction_mode == "predictions":
        typer.echo(
            "This run used a predictions file whose path was not recorded; "
            "re-grade candidate runs with the original predictions file.",
            err=True,
        )
        raise typer.Exit(1)

    run_evaluation(
        dataset_name=resolve_dataset(dataset),
        split=split,
        instance_ids=list(instance_ids) if instance_ids else None,
        predictions_path=prediction_mode,
        max_workers=1,
        open_file_limit=4096,
        run_id=run_id,
        timeout=1800,
        rewrite_reports=True,
        modal=False,
        # a run made against a task repo has to be re-graded against the same tests,
        # or the dataset's copy silently overrides them and the verdict changes
        task_repo=recorded.get("task_repo"),
    )
