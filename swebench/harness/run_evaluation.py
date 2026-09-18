from __future__ import annotations

import docker
import json
from datetime import datetime, timezone
import os
import platform
import urllib.request
import traceback

if platform.system() == "Linux":
    import resource

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pathlib import Path, PurePosixPath

from swebench.image_builder.constants import CONTAINER_USER, CONTAINER_WORKDIR
from swebench.harness.constants import (
    APPLY_PATCH_FAIL,
    APPLY_PATCH_PASS,
    CONTAINER_PATCH_FILE,
    LOG_REPORT,
    LOG_RUN_METADATA,
    LOG_INSTANCE,
    LOG_TEST_OUTPUT,
    RUN_EVALUATION_LOG_DIR,
    START_TEST_OUTPUT,
)
from swebench.harness.docker_utils import (
    cleanup_container,
    copy_to_container,
    exec_run_with_timeout,
)
import logging
from swebench.harness.grading import get_eval_report
from swebench.harness.reporting import make_run_report
from swebench.harness.modal_eval import (
    run_instances_modal,
    validate_modal_credentials,
)
from swebench.types import TestSpec
from swebench.harness.utils import make_test_spec
from swebench.task.repo import asset_path, load_task_repo
from swebench.harness.utils import (
    EvaluationError,
    load_swebench_dataset,
    get_predictions_from_file,
    run_threadpool,
    str2bool,
)

from swebench.logger import setup_logger, close_logger

GIT_APPLY_CMDS = [
    "git apply --verbose",
    "git apply --verbose --3way",
    "git apply --verbose --reject",
    "patch --batch --forward --fuzz=5 -p1 -i",
]

DOCKER_CLIENT_TIMEOUT = int(os.environ.get("SWEBENCH_DOCKER_TIMEOUT", "1800"))
DOCKER_CLIENT_POOL_SIZE = int(os.environ.get("SWEBENCH_DOCKER_POOL_SIZE", "128"))


def _docker_client() -> docker.DockerClient:
    return docker.from_env(
        timeout=DOCKER_CLIENT_TIMEOUT,
        max_pool_size=DOCKER_CLIENT_POOL_SIZE,
    )


def create_container(
    test_spec: TestSpec,
    client: docker.DockerClient,
    run_id: str,
    logger: logging.Logger,
):
    """
    Creates a container from an instance image for running evaluation.

    Args:
        test_spec (TestSpec): Test spec with evaluation details
        client (docker.DockerClient): Docker client for creating the container
        run_id (str): Run ID identifying process, used for the container name
        logger (logging.Logger): Logger to use for logging the creation process
    """
    container = None
    try:
        # Check if the image exists
        try:
            client.images.get(test_spec.image)
        except docker.errors.ImageNotFound:
            try:
                logger.info("Image not found locally, attempting to pull...")
                client.images.pull(test_spec.image)
            except docker.errors.ImageNotFound:
                raise EvaluationError(
                    test_spec.instance_id,
                    f"Image {test_spec.image} not found for {test_spec.instance_id}",
                    logger,
                )

        logger.info(f"Creating container for {test_spec.instance_id}...")

        container_name = f"sweb.eval.{test_spec.instance_id.lower()}.{run_id}"
        # Remove any existing container with this name (handles ghost containers)
        try:
            old = client.containers.get(container_name)
            old.remove(force=True)
            logger.info(f"Removed existing container {container_name}")
        except docker.errors.NotFound:
            pass
        except Exception:
            pass
        try:
            container = client.containers.create(
                image=test_spec.image,
                name=container_name,
                user=CONTAINER_USER,
                detach=True,
                command="tail -f /dev/null",
                # Docker's default seccomp profile only permits CLONE_NEWUSER with
                # CAP_SYS_ADMIN, which browser sandboxes need (e.g. openlayers karma)
                cap_add=["SYS_ADMIN"],
            )
        except docker.errors.APIError as e:
            if "409" in str(e) or "Conflict" in str(e):
                # Ghost container — use a unique suffix
                import time

                container_name = f"{container_name}.{int(time.time())}"
                logger.info(f"Retrying with unique name: {container_name}")
                container = client.containers.create(
                    image=test_spec.image,
                    name=container_name,
                    user=CONTAINER_USER,
                    detach=True,
                    command="tail -f /dev/null",
                    # Docker's default seccomp profile only permits CLONE_NEWUSER with
                    # CAP_SYS_ADMIN, which browser sandboxes need (e.g. openlayers karma)
                    cap_add=["SYS_ADMIN"],
                )
            else:
                raise
        logger.info(f"Container for {test_spec.instance_id} created: {container.id}")
        return container
    except Exception as e:
        logger.error(f"Error creating container for {test_spec.instance_id}: {e}")
        logger.info(traceback.format_exc())
        cleanup_container(client, container, logger)
        raise EvaluationError(test_spec.instance_id, str(e), logger) from e


def _resolve_asset_bytes(asset: dict, task_repo: str | None, logger) -> bytes | None:
    """Read an asset from the task repo if there is one, else fetch its url."""
    if task_repo is not None:
        local = asset_path(task_repo, asset["instance_id"], asset["path"])
        if local.is_file():
            return local.read_bytes()
    if not asset.get("url"):
        logger.warning(f"No asset for {asset['instance_id']} at {asset['path']}")
        return None
    try:
        with urllib.request.urlopen(asset["url"], timeout=60) as resp:
            return resp.read()
    except Exception as e:
        logger.warning(f"Could not fetch image asset {asset['url']}: {e}")
        return None


def _stage_image_assets(
    container, test_spec, log_dir: Path, logger, task_repo: str | None = None
) -> list[str]:
    """Stage a patch's binary assets in the container; return restore commands.

    A text patch cannot carry binary files (e.g. expected.png rendering baselines),
    so the dataset lists them in image_assets. They must land in the working tree
    *after* the eval script's `rm -f` + `git apply`, so they arrive with the patch
    rather than being baked into the image -- test data in the image would be
    visible to anything with a shell in it.
    """
    declared = test_spec.image_assets or {}
    assets = []
    for key in ("test_patch", "patch"):
        for entry in declared.get(key) or []:
            if entry.get("path"):
                assets.append({**entry, "instance_id": test_spec.instance_id})
    if not assets:
        return []
    staging = Path(log_dir) / "image_assets"
    staging.mkdir(parents=True, exist_ok=True)
    container.exec_run("mkdir -p /image_assets", user="root")
    restore, from_mirror = [], 0
    for asset in assets:
        data = _resolve_asset_bytes(asset, task_repo, logger)
        if data is None:
            continue
        if (
            task_repo is not None
            and asset_path(task_repo, asset["instance_id"], asset["path"]).is_file()
        ):
            from_mirror += 1
        flat = asset["path"].replace("/", "__")
        local = staging / flat
        local.write_bytes(data)
        copy_to_container(container, local, PurePosixPath("/image_assets") / flat)
        restore.append(
            f"mkdir -p $(dirname {asset['path']}) && cp /image_assets/{flat} {asset['path']}"
        )
    if restore:
        logger.info(
            f"Staged {len(restore)} patch asset(s) for restore after git apply "
            f"({from_mirror} from the local mirror, {len(restore) - from_mirror} fetched)"
        )
    return restore


def _inject_asset_restore(eval_script: str, restore_cmds: list[str]) -> str:
    """Insert asset-restore commands just before the test-output start marker."""
    if not restore_cmds:
        return eval_script
    lines = eval_script.split("\n")
    for idx, line in enumerate(lines):
        if START_TEST_OUTPUT in line:
            return "\n".join(lines[:idx] + restore_cmds + lines[idx:])
    return eval_script + "\n" + "\n".join(restore_cmds)


def run_instance(
    test_spec: TestSpec,
    pred: dict,
    client: docker.DockerClient,
    run_id: str,
    timeout: int | None = None,
    rewrite_reports: bool = False,
    skip_patch: bool = False,
    task_repo: str | None = None,
):
    """
    Run a single instance with the given prediction.

    Args:
        test_spec (TestSpec): TestSpec instance with pre-built image
        pred (dict): Prediction w/ model_name_or_path, model_patch, instance_id
        client (docker.DockerClient): Docker client
        run_id (str): Run ID
        timeout (int): Timeout for running tests
        rewrite_reports (bool): True if eval run is just to reformat existing report
        skip_patch (bool): True to skip applying model patch (negative test mode)
    """
    # Set up logging directory
    instance_id = test_spec.instance_id
    model_name_or_path = pred.get("model_name_or_path", "None").replace("/", "__")
    log_dir = RUN_EVALUATION_LOG_DIR / run_id / model_name_or_path / instance_id

    # Set up report file
    report_path = log_dir / LOG_REPORT
    if rewrite_reports:
        test_output_path = log_dir / LOG_TEST_OUTPUT
        if not test_output_path.exists():
            raise ValueError(f"Test output file {test_output_path} does not exist")
        report = get_eval_report(
            test_spec=test_spec,
            prediction=pred,
            test_log_path=test_output_path,
            include_tests_status=True,
        )
        # Write report to report.json
        with open(report_path, "w") as f:
            f.write(json.dumps(report, indent=4))
        return instance_id, report
    if report_path.exists():
        return instance_id, json.loads(report_path.read_text())

    # Set up logger
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / LOG_INSTANCE
    logger = setup_logger(instance_id, log_file)

    # Run the instance
    container = None
    try:
        # Create container from image
        container = create_container(test_spec, client, run_id, logger)
        container.start()
        logger.info(f"Container for {instance_id} started: {container.id}")

        if not skip_patch:
            # Copy model prediction as patch file to container
            patch_file = Path(log_dir / "patch.diff")
            patch_file.write_text(
                pred["model_patch"] or "",
                newline="\n",
            )
            logger.info(
                f"Intermediate patch for {instance_id} written to {patch_file}, now applying to container..."
            )
            copy_to_container(
                container, patch_file, PurePosixPath(CONTAINER_PATCH_FILE)
            )

            # Attempt to apply patch to container
            applied_patch = False
            for attempt, git_apply_cmd in enumerate(GIT_APPLY_CMDS):
                if attempt:
                    # a failed attempt (notably --reject) leaves partial state behind,
                    # which makes every later command fail; restart from a pristine tree
                    container.exec_run(
                        ["/bin/bash", "-c", "git checkout -- . ; git clean -fd"],
                        workdir=CONTAINER_WORKDIR,
                        user=CONTAINER_USER,
                    )
                val = container.exec_run(
                    f"{git_apply_cmd} {CONTAINER_PATCH_FILE}",
                    workdir=CONTAINER_WORKDIR,
                    user=CONTAINER_USER,
                )
                if val.exit_code == 0:
                    logger.info(f"{APPLY_PATCH_PASS}:\n{val.output.decode('utf-8')}")
                    applied_patch = True
                    break
                else:
                    logger.info(f"Failed to apply patch to container: {git_apply_cmd}")
            if not applied_patch:
                # the chain can leave the patch fully applied while each command still exited non-zero
                reverse_check = container.exec_run(
                    f"git apply --check --reverse {CONTAINER_PATCH_FILE}",
                    workdir=CONTAINER_WORKDIR,
                    user=CONTAINER_USER,
                )
                if reverse_check.exit_code == 0:
                    logger.info(f"{APPLY_PATCH_PASS}: verified already applied")
                    applied_patch = True
            if not applied_patch:
                logger.info(f"{APPLY_PATCH_FAIL}:\n{val.output.decode('utf-8')}")
                raise EvaluationError(
                    instance_id,
                    f"{APPLY_PATCH_FAIL}:\n{val.output.decode('utf-8')}",
                    logger,
                )
        else:
            logger.info(f"Skipping model patch for {instance_id} (--no-patch mode)")

        # Get git diff before running eval script
        git_diff_output_before = (
            container.exec_run(
                "git -c core.fileMode=false diff", workdir=CONTAINER_WORKDIR
            )
            .output.decode("utf-8")
            .strip()
        )
        logger.info(f"Git diff before:\n{git_diff_output_before}")

        # Materialize multimodal binary assets (e.g. expected.png rendering
        # baselines). A text test_patch cannot carry them, so the dataset ships
        # them as urls in image_assets; without this the tests run against a
        # missing baseline and error out.
        restore_cmds = _stage_image_assets(
            container, test_spec, log_dir, logger, task_repo
        )

        eval_file = Path(log_dir / "eval.sh")
        eval_file.write_text(
            _inject_asset_restore(test_spec.eval_script, restore_cmds),
            newline="\n",
        )
        logger.info(
            f"Eval script for {instance_id} written to {eval_file}; copying to container..."
        )
        copy_to_container(container, eval_file, PurePosixPath("/eval.sh"))

        # Run eval script, write output to logs
        test_output, timed_out, total_runtime = exec_run_with_timeout(
            container, "/bin/bash /eval.sh", timeout
        )
        test_output_path = log_dir / LOG_TEST_OUTPUT
        logger.info(f"Test runtime: {total_runtime:_.2f} seconds")
        with open(test_output_path, "w") as f:
            f.write(test_output)
            logger.info(f"Test output for {instance_id} written to {test_output_path}")
            if timed_out:
                f.write(f"\n\nTimeout error: {timeout} seconds exceeded.")
                raise EvaluationError(
                    instance_id,
                    f"Test timed out after {timeout} seconds.",
                    logger,
                )

        # Get git diff after running eval script (ignore permission changes)
        git_diff_output_after = (
            container.exec_run(
                "git -c core.fileMode=false diff", workdir=CONTAINER_WORKDIR
            )
            .output.decode("utf-8")
            .strip()
        )

        # Check if git diff changed after running eval script
        logger.info(f"Git diff after:\n{git_diff_output_after}")
        if git_diff_output_after != git_diff_output_before:
            logger.info("Git diff changed after running eval script")

        # Get report from test output
        logger.info(f"Grading answer for {instance_id}...")
        report = get_eval_report(
            test_spec=test_spec,
            prediction=pred,
            test_log_path=test_output_path,
            include_tests_status=True,
        )
        logger.info(
            f"report: {report}\n"
            f"Result for {instance_id}: resolved: {report[instance_id]['resolved']}"
        )

        # Write report to report.json
        with open(report_path, "w") as f:
            f.write(json.dumps(report, indent=4))
        return instance_id, report
    except EvaluationError as e:
        error_msg = traceback.format_exc()
        logger.info(error_msg)
        print(e)
    except Exception as e:
        error_msg = (
            f"Error in evaluating model for {instance_id}: {e}\n"
            f"{traceback.format_exc()}\n"
            f"Check ({logger.log_file}) for more information."
        )
        logger.error(error_msg)
    finally:
        # Remove instance container + image, close logger
        cleanup_container(client, container, logger)
        close_logger(logger)
    return


def run_instances(
    predictions: dict,
    instances: list,
    max_workers: int,
    run_id: str,
    timeout: int,
    rewrite_reports: bool = False,
    skip_patch: bool = False,
    task_repo: str | None = None,
):
    """
    Run all instances for the given predictions in parallel.
    Expects instances to have pre-built images.

    Args:
        predictions (dict): Predictions dict generated by the model
        instances (list): List of instances with 'image' field
        max_workers (int): Maximum number of workers
        run_id (str): Run ID
        timeout (int): Timeout for running tests
        rewrite_reports (bool): True if eval run is just to reformat existing report
    """
    client = _docker_client()
    test_specs = [make_test_spec(instance) for instance in instances]

    # run instances in parallel
    payloads = []
    for test_spec in test_specs:
        payloads.append(
            (
                test_spec,
                predictions[test_spec.instance_id],
                client,
                run_id,
                timeout,
                rewrite_reports,
                skip_patch,
                task_repo,
            )
        )

    # run instances in parallel
    print(f"Running {len(instances)} instances...")
    run_threadpool(run_instance, payloads, max_workers)
    print("All instances run.")


def write_run_metadata(
    run_id: str, dataset_name: str, split: str, task_repo: str | None
) -> Path:
    """Record what this run graded against.

    Re-grading needs the expected tests and the log parser, which live in the
    dataset, not in the run's logs. Without this a later `swebench report` has to
    be told the dataset again, and gets it wrong silently if told the wrong one.
    """
    path = RUN_EVALUATION_LOG_DIR / run_id / LOG_RUN_METADATA
    path.parent.mkdir(parents=True, exist_ok=True)
    # a re-grade passes no task repo, and overwriting the recorded one with null
    # loses the only record of which tests the run was graded against
    if task_repo is None and path.is_file():
        task_repo = json.loads(path.read_text()).get("task_repo")
    path.write_text(
        json.dumps(
            {
                "dataset": dataset_name,
                "split": split,
                "task_repo": task_repo,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
            indent=2,
        )
        + "\n"
    )
    return path


def read_run_metadata(run_id: str) -> dict | None:
    """What a previous run graded against, if it recorded it."""
    path = RUN_EVALUATION_LOG_DIR / run_id / LOG_RUN_METADATA
    return json.loads(path.read_text()) if path.is_file() else None


def load_instances(
    dataset_name: str, split: str, instance_ids: list | None, task_repo: str | None
) -> list:
    """Instances come from the task repo when one is given, else from the dataset.

    A dataset is already one split; a task repo holds every split at once, so the
    split has to be applied here or a run picks up whatever else is in the tree --
    the multimodal repo would evaluate its dev and deprecated tasks alongside test.

    Named ids are honoured from any split, matching `select_tasks`: an instance
    being repaired can be run by name while it sits in an unpublished split.
    """
    if not task_repo:
        return load_swebench_dataset(dataset_name, split, instance_ids)
    tasks = load_task_repo(task_repo, instance_ids)
    if instance_ids:
        return tasks
    wanted = [task for task in tasks if task.get("split") == split]
    if not wanted:
        available = sorted({task["split"] for task in tasks if task.get("split")})
        raise ValueError(
            f"{task_repo} has no tasks in split {split!r}. "
            f"It has: {' '.join(available) or 'none'}"
        )
    return wanted


def get_dataset_from_preds(
    dataset_name: str,
    split: str,
    instance_ids: list,
    predictions: dict,
    run_id: str,
    rewrite_reports: bool,
    exclude_completed: bool = True,
    task_repo: str | None = None,
):
    """
    Return only instances that have predictions and are in the dataset.
    If instance_ids is provided, only return instances with those IDs.
    If exclude_completed is True, only return instances that have not been run yet.
    """
    # load dataset
    dataset = load_instances(dataset_name, split, None, task_repo)
    dataset_ids = {i["instance_id"] for i in dataset}

    if instance_ids:
        # check that all instance IDs have predictions
        missing_preds = set(instance_ids) - set(predictions.keys())
        if missing_preds:
            print(
                f"Warning: Missing predictions for {len(missing_preds)} instance IDs."
            )

    # check that all prediction IDs are in the dataset
    prediction_ids = set(predictions.keys())
    if prediction_ids - dataset_ids:
        raise ValueError(
            (
                "Some prediction IDs not found in dataset!"
                f"\nMissing IDs:\n{' '.join(prediction_ids - dataset_ids)}"
            )
        )
    if instance_ids:
        dataset = [i for i in dataset if i["instance_id"] in instance_ids]

    if rewrite_reports:
        # we only return instances that have existing test outputs
        test_output_ids = set()
        for instance in dataset:
            if instance["instance_id"] not in predictions:
                continue
            prediction = predictions[instance["instance_id"]]
            test_output_file = (
                RUN_EVALUATION_LOG_DIR
                / run_id
                / prediction["model_name_or_path"].replace("/", "__")
                / prediction["instance_id"]
                / "test_output.txt"
            )
            if test_output_file.exists():
                test_output_ids.add(instance["instance_id"])
        dataset = [
            i
            for i in dataset
            if i["instance_id"] in prediction_ids
            and i["instance_id"] in test_output_ids
        ]
        return dataset

    # check which instance IDs have already been run
    completed_ids = set()
    for instance in dataset:
        if instance["instance_id"] not in prediction_ids:
            # skip instances without predictions
            continue
        prediction = predictions[instance["instance_id"]]
        report_file = (
            RUN_EVALUATION_LOG_DIR
            / run_id
            / prediction["model_name_or_path"].replace("/", "__")
            / prediction["instance_id"]
            / LOG_REPORT
        )
        if report_file.exists():
            completed_ids.add(instance["instance_id"])

    if completed_ids and exclude_completed:
        # filter dataset to only instances that have not been run
        print(f"{len(completed_ids)} instances already run, skipping...")
        dataset = [i for i in dataset if i["instance_id"] not in completed_ids]

    empty_patch_ids = {
        k
        for k, v in predictions.items()
        if v["model_patch"] == "" or v["model_patch"] is None
    }

    # filter dataset to only instances with predictions
    dataset = [
        i
        for i in dataset
        if i["instance_id"] in prediction_ids
        and i["instance_id"] not in empty_patch_ids
    ]
    return dataset


def _build_before_eval(dataset, dataset_name, split, task_repo, max_workers, client):
    """Build this run's images from a task repo instead of trusting the registry.

    Without this a failed build is invisible: the image is pulled instead, so a stale
    published image can report a clean pass. Verification is by the image name the
    evaluation will actually use, so a naming mismatch cannot pass for a build.
    """
    from swebench.image_builder.docker_build import build_instance_images
    from swebench.image_builder.image_spec import get_image_specs_from_dataset
    from swebench.image_builder.prepare_images import resolve_task_repo
    from swebench.task.repo import load_dockerfiles, task_paths

    wanted = {d["instance_id"]: make_test_spec(d).image for d in dataset}
    # namespace and tag come from the image the dataset names, so built tags match
    sample = next(iter(wanted.values()))
    namespace = sample.split("/")[0] if "/" in sample else None
    tag = sample.rsplit(":", 1)[1] if ":" in sample.rsplit("/", 1)[-1] else "latest"

    print(f"Building {len(wanted)} image(s) from {task_repo} before evaluating...")
    with resolve_task_repo(task_repo) as repo_path:
        dockerfiles = load_dockerfiles(repo_path, list(wanted))
        contexts = task_paths(repo_path, list(wanted))
        image_specs = get_image_specs_from_dataset(
            dataset, dockerfiles, namespace, tag, contexts
        )
        if not image_specs:
            print("No Dockerfiles matched these instances; nothing was built.")
        else:
            build_instance_images(
                client=client,
                image_specs=image_specs,
                force_rebuild=True,
                max_workers=max_workers,
            )

    # trust the registry only where a build did not produce the image
    missing = []
    for iid, image in wanted.items():
        try:
            client.images.get(image)
        except docker.errors.ImageNotFound:
            missing.append((iid, image))
    if not missing:
        print(f"Built {len(wanted)} image(s) locally; none pulled.")
        return
    print(
        f"BUILD FAILED for {len(missing)} instance(s): {', '.join(i for i, _ in sorted(missing))}"
    )
    for iid, image in missing:
        try:
            client.images.pull(image)
            print(f"  {iid}: build failed; FELL BACK to the published image {image}")
        except docker.errors.ImageNotFound:
            print(f"  {iid}: build failed and no published image exists; it will error")


def main(
    dataset_name: str,
    split: str,
    instance_ids: list,
    predictions_path: str,
    max_workers: int,
    open_file_limit: int,
    run_id: str,
    timeout: int,
    rewrite_reports: bool,
    modal: bool,
    task_repo: str | None = None,
):
    """
    Run evaluation harness for the given dataset and predictions.
    """
    if dataset_name == "SWE-bench/SWE-bench_Multimodal" and split == "test":
        print(
            "ℹ️ Running local evaluation for the test split of SWE-bench Multimodal. "
            "You may also use sb-cli (https://github.com/swe-bench/sb-cli/) to submit predictions to the hosted evaluation."
        )

    # Modal builds its own images remotely, so a task repo's Dockerfiles would be
    # ignored while its tests were used -- the run would report on a tree it never
    # built. Refused here, before any work, rather than silently proving the wrong thing.
    if modal and task_repo:
        raise ValueError(
            "--modal cannot build from a task repo: it builds images remotely, so the "
            "repo's Dockerfiles would be ignored while its tests were used. Drop "
            "--task-repo to run on Modal, or drop --modal to build the repo."
        )

    # set open file limit
    assert len(run_id) > 0, "Run ID must be provided"
    # load predictions as map of instance_id to prediction
    predictions = get_predictions_from_file(
        predictions_path, dataset_name, split, task_repo, instance_ids
    )
    predictions = {pred["instance_id"]: pred for pred in predictions}
    write_run_metadata(run_id, dataset_name, split, task_repo)

    # get dataset from predictions
    dataset = get_dataset_from_preds(
        dataset_name,
        split,
        instance_ids,
        predictions,
        run_id,
        rewrite_reports,
        task_repo=task_repo,
    )
    full_dataset = load_instances(dataset_name, split, instance_ids, task_repo)

    if modal:
        # run instances on Modal
        if not dataset:
            print("No instances to run.")
        else:
            validate_modal_credentials()
            run_instances_modal(predictions, dataset, full_dataset, run_id, timeout)
        return

    # run instances locally
    if platform.system() == "Linux":
        resource.setrlimit(resource.RLIMIT_NOFILE, (open_file_limit, open_file_limit))
    client = _docker_client()

    if not dataset:
        print("No instances to run.")
        return make_run_report(predictions, full_dataset, run_id, client)
    else:
        # a re-grade reads existing logs and starts no container, so building the
        # images it names would cost hours and change nothing
        if task_repo and not rewrite_reports:
            _build_before_eval(
                dataset, dataset_name, split, task_repo, max_workers, client
            )
        # run instances (images assumed to be pre-built)
        run_instances(
            predictions,
            dataset,
            max_workers,
            run_id,
            timeout,
            rewrite_reports=rewrite_reports,
            task_repo=task_repo,
        )

    # make final report
    return make_run_report(predictions, full_dataset, run_id, client)


if __name__ == "__main__":
    parser = ArgumentParser(
        description="Run evaluation harness for the given dataset and predictions.",
        formatter_class=ArgumentDefaultsHelpFormatter,
    )

    # Common args
    parser.add_argument(
        "-d",
        "--dataset_name",
        default="SWE-bench/SWE-bench_Lite",
        type=str,
        help="Name of dataset or path to JSON file.",
    )
    parser.add_argument(
        "-s", "--split", type=str, default="test", help="Split of the dataset"
    )
    parser.add_argument(
        "-i",
        "--instance_ids",
        nargs="+",
        type=str,
        help="Instance IDs to run (space separated)",
    )
    parser.add_argument(
        "-p",
        "--predictions_path",
        type=str,
        help="Path to predictions file - if 'gold', uses gold predictions",
        required=True,
    )

    # Local execution args
    parser.add_argument(
        "--max_workers",
        type=int,
        default=4,
        help="Maximum number of workers (should be <= 75%% of CPU cores)",
    )
    parser.add_argument(
        "--open_file_limit", type=int, default=4096, help="Open file limit"
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=1_800,
        help="Timeout (in seconds) for running tests for each instance",
    )
    parser.add_argument(
        "-id", "--run_id", type=str, required=True, help="Run ID - identifies the run"
    )
    parser.add_argument(
        "--rewrite_reports",
        type=str2bool,
        default=False,
        help="Doesn't run new instances, only writes reports for instances with existing test outputs",
    )
    # Modal execution args
    parser.add_argument("--modal", type=str2bool, default=False, help="Run on Modal")

    args = parser.parse_args()
    main(**vars(args))
