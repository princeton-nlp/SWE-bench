"""`swebench images` — build, check and clean instance images."""

from typing import Optional

import typer

images_app = typer.Typer(
    name="images",
    help="Build, check and clean instance images.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@images_app.command("build")
def build(
    task_repo: str = typer.Argument(
        ..., metavar="TASK_REPO", help="Path to a task repo"
    ),
    datasets: Optional[list[str]] = typer.Option(
        None, "-d", "--dataset", help="Only these datasets (repeatable)"
    ),
    instance_ids: Optional[list[str]] = typer.Option(
        None, "-i", "--instance", help="Only these instances (repeatable)"
    ),
    split: Optional[str] = typer.Option(
        None, "-s", "--split", help="Only tasks in this split"
    ),
    workers: int = typer.Option(4, "-j", "--workers"),
    force_rebuild: bool = typer.Option(False, "--force-rebuild"),
    namespace: Optional[str] = typer.Option(
        None, "-n", "--namespace", help="Registry namespace to tag for"
    ),
    tag: str = typer.Option("latest", "--tag"),
    dry_run: bool = typer.Option(False, "--dry-run", help="List what would be built"),
    open_file_limit: int = typer.Option(65536, "--open-file-limit"),
):
    """Build images ahead of an evaluation, from a task repo.

    Builds everything the repo publishes. Use --split or -i to narrow the build;
    an explicit instance may name a task in an unpublished split.

    [yellow][bold]Examples:[/bold][/yellow]

        swebench images build ~/swe-bench-tasks -j 8

        swebench images build ~/swe-bench-multimodal-tasks -i carbon-design-system__carbon-10188

        swebench images build ~/swe-bench-tasks --dry-run
    """
    from swebench.image_builder.prepare_images import main as prepare_images
    from swebench.task.publish import CheckFailed
    from swebench.task.repo import UnknownDataset

    try:
        prepare_images(
            task_repo=task_repo,
            instance_ids=list(instance_ids) if instance_ids else None,
            datasets=list(datasets) if datasets else None,
            max_workers=workers,
            force_rebuild=force_rebuild,
            open_file_limit=open_file_limit,
            namespace=namespace,
            tag=tag,
            dry_run=dry_run,
            split=split,
        )
    except (CheckFailed, UnknownDataset, ValueError, RuntimeError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e


@images_app.command("check")
def check(
    task_repo: str = typer.Argument(
        ..., metavar="TASK_REPO", help="Path to a task repo"
    ),
    datasets: Optional[list[str]] = typer.Option(
        None, "-d", "--dataset", help="Only these datasets (repeatable)"
    ),
    instance_ids: Optional[list[str]] = typer.Option(
        None, "-i", "--instance", help="Only these instances (repeatable)"
    ),
    workers: int = typer.Option(16, "-j", "--workers"),
):
    """Report which of a task repo's images are missing from the registry.

    Catches a stale or partially-pushed image set before an evaluation spends
    hours discovering it one instance at a time.

    [yellow][bold]Examples:[/bold][/yellow]

        swebench images check ~/swe-bench-tasks

        swebench images check ~/swe-bench-multilingual-tasks -j 32
    """
    from concurrent.futures import ThreadPoolExecutor

    import docker

    from swebench.task.repo import UnknownDataset, select_tasks

    client = docker.from_env()
    try:
        instances = select_tasks(
            task_repo,
            list(instance_ids) if instance_ids else None,
            list(datasets) if datasets else None,
        )
    except UnknownDataset as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    names = sorted({i["image"] for i in instances if i.get("image")})
    if not names:
        typer.echo("dataset rows carry no image field")
        raise typer.Exit(1)

    def present(name: str) -> tuple[str, bool]:
        try:
            client.images.get_registry_data(name)
            return name, True
        except Exception:
            return name, False

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(present, names))

    missing = [n for n, ok in results if not ok]
    typer.echo(f"{len(names) - len(missing)}/{len(names)} images present")
    for name in missing:
        typer.echo(f"  missing {name}")
    raise typer.Exit(1 if missing else 0)


@images_app.command("clean")
def clean(
    run_id: Optional[str] = typer.Option(
        None, "--run-id", help="Remove containers from this run"
    ),
    instance_ids: Optional[list[str]] = typer.Option(None, "-i", "--instance"),
    predictions: Optional[str] = typer.Option(None, "-p", "--predictions"),
):
    """Remove leftover evaluation containers.

    A killed run leaves containers holding their names, and the next attempt
    fails with a 409 conflict.

    [yellow][bold]Examples:[/bold][/yellow]

        swebench images clean --run-id my-run

        swebench images clean -i astropy__astropy-12907
    """
    from swebench.harness.remove_containers import main as remove_containers

    remove_containers(
        instance_ids=list(instance_ids) if instance_ids else None,
        predictions_path=predictions,
        run_id=run_id,
    )


@images_app.command("push")
def push(
    task_repo: str = typer.Argument(
        ..., metavar="TASK_REPO", help="Path to a task repo"
    ),
    datasets: Optional[list[str]] = typer.Option(
        None, "-d", "--dataset", help="Only these datasets (repeatable)"
    ),
    instance_ids: Optional[list[str]] = typer.Option(
        None, "-i", "--instance", help="Only these instances (repeatable)"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be pushed"),
):
    """Push each task's image to the registry, under the name its task.yaml declares.

    The dataset tells the harness which image to pull, so the pushed name has to
    match. Images that are not built locally are reported, not silently skipped.

    [yellow][bold]Examples:[/bold][/yellow]

        swebench images push ~/swe-bench-multilingual-tasks --dry-run

        swebench images push ~/swe-bench-multilingual-tasks -i google__gson-2479
    """
    from swebench.task.publish import CheckFailed, push_images, summarize
    from swebench.task.repo import UnknownDataset

    try:
        plan = push_images(
            task_repo,
            instance_ids=list(instance_ids) if instance_ids else None,
            dry_run=dry_run,
            datasets=list(datasets) if datasets else None,
        )
    except (CheckFailed, UnknownDataset) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    typer.echo(summarize(plan))
