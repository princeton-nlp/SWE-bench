import docker
import json
import resource
import traceback
import uuid

from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tqdm import tqdm

from swebench.harness.utils import load, str2bool
from swebench.harness.grading import get_pred_report
from swebench.harness.docker_utils import (
    cleanup_image,
    copy_to_container,
    exec_run_with_timeout,
    cleanup_container,
    list_images,
    should_remove,
    clean_images,
)
from swebench.harness.docker_build import (
    build_container,
    build_env_images,
    INSTANCE_IMAGE_BUILD_DIR,
    close_logger,
    setup_logger,
)
from swebench.harness.dataset import make_test_spec


RUN_INSTANCE_LOG_DIR = Path("run_instance_logs")


class EvaluationError(Exception):
    def __init__(self, instance_id, message, logger):
        super().__init__(message)
        self.instance_id = instance_id
        self.log_file = logger.log_file
        self.logger = logger

    def __str__(self):
        log_msg = traceback.format_exc()
        self.logger.info(log_msg)
        return (
            f"{self.instance_id}: {super().__str__()}\n"
            f"Check ({self.log_file}) for more information."
        )


def run_instance(test_spec, pred, rm_image, force_rebuild, client, session_id, timeout=None):
    instance_id = test_spec.instance_id
    model_name_or_path = pred.get("model_name_or_path", "None").replace("/", "__")
    log_dir = RUN_INSTANCE_LOG_DIR / model_name_or_path / instance_id
    log_dir.mkdir(parents=True, exist_ok=True)
    build_dir = INSTANCE_IMAGE_BUILD_DIR / test_spec.instance_image_key.replace(":", "__")
    image_build_link = log_dir / "image_build_dir"
    if not image_build_link.exists():
        try:
            image_build_link.symlink_to(build_dir, target_is_directory=True)
        except:
            # some error, idk why
            pass
    log_file = log_dir / "run_instance.log"
    report_path = log_dir / "report.json"
    if report_path.exists():
        return instance_id, json.loads(report_path.read_text())
    logger = setup_logger(instance_id, log_file)
    container = None
    try:
        container = build_container(test_spec, client, session_id, logger, rm_image, force_rebuild)
        container.start()
        logger.info(f"Container for {instance_id} started: {container.id}")

        patch_file = log_dir / "patch.diff"
        with open(patch_file, "w") as f:
            f.write(pred["model_patch"])
        logger.info(
            f"Intermediate patch for {instance_id} written to {patch_file}, now applying to container..."
        )
        copy_to_container(container, patch_file, Path("/tmp/patch.diff"))
        val = container.exec_run(
            "git apply -v /tmp/patch.diff",
            workdir="/testbed",
            user="root",
        )
        if val.exit_code != 0:
            logger.info(f"Error applying patch:\n{val.output.decode('utf-8')}")
            raise EvaluationError(
                instance_id,
                f"Error applying patch:\n{val.output.decode('utf-8')}",
                logger,
            )

        git_diff_output_before = (
            container.exec_run("git diff", workdir="/testbed").output.decode("utf-8").strip()
        )
        logger.info(f"Git diff before:\n{git_diff_output_before}")

        # result = container.exec_run("/bin/bash /eval.sh")
        result = exec_run_with_timeout(container, "/bin/bash /eval.sh", timeout=timeout)
        test_output = result.decode("utf-8")
        test_output_path = log_dir / "test_output.txt"
        with open(test_output_path, "w") as f:
            f.write(test_output)
        logger.info(f"Test output for {instance_id} written to {test_output_path}")

        git_diff_output_after = (
            container.exec_run("git diff", workdir="/testbed").output.decode("utf-8").strip()
        )
        logger.info(f"Git diff after:\n{git_diff_output_after}")
        if git_diff_output_after != git_diff_output_before:
            logger.info(f"Git diff changed after running eval script")
            # "Git diff changed after running eval script"

        logger.info(f"Grading answer for {instance_id}...")
        report = get_pred_report(
            test_spec=test_spec,
            prediction=pred,
            log_path=test_output_path,
            include_tests_status=True,
        )
        logger.info(
            f"report: {report}\n"
            f"Result for {instance_id}: resolved: {report[instance_id]['resolved']}"
        )

        with open(report_path, "w") as f:
            f.write(json.dumps(report, indent=4))
        return instance_id, report
    except EvaluationError as e:
        raise EvaluationError(instance_id, str(e), logger) from e
    except Exception as e:
        logger.error(f"Error in evaluating model for {instance_id}: {e}")
        logger.info(traceback.format_exc())
        raise EvaluationError(instance_id, str(e), logger) from e
    finally:
        cleanup_container(client, container, logger)
        cleanup_image(client, test_spec.instance_image_key, rm_image, logger)
        close_logger(logger)


def run_instances(predictions, instances, cache, clean, force_rebuild, max_workers, session_id, timeout):
    client = docker.from_env()
    test_specs = list(map(make_test_spec, instances))
    instance_image_ids = {x.instance_image_key for x in test_specs}
    existing_images = {
        tag for i in client.images.list(all=True) for tag in i.tags if tag in instance_image_ids
    }
    if not force_rebuild and len(existing_images):
        print(f"Found {len(existing_images)} existing instance images. Will reuse them.")
    print(f"Running {len(instances)} instances...")
    with tqdm(total=len(instances), smoothing=0) as pbar:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    run_instance,
                    spec,
                    predictions[spec.instance_id],
                    should_remove(
                        spec.instance_image_key,
                        cache,
                        clean,
                        existing_images,
                    ),
                    force_rebuild,
                    client,
                    session_id,
                    timeout,
                ): None
                for spec in test_specs
            }
            for future in as_completed(futures):
                pbar.update(1)
                try:
                    future.result()
                except EvaluationError as e:
                    print(f"EvaluationError {e.instance_id}: {e}")
                    continue
                except Exception as e:
                    traceback.print_exc()
                    continue
    print("All instances run.")


def get_dataset_from_preds(dataset_name, split, instance_ids, predictions, exclude_completed=True):
    dataset = load(dataset_name, split)
    dataset_ids = {i["instance_id"] for i in dataset}
    if instance_ids:
        instance_ids = set(instance_ids)
        if instance_ids - dataset_ids:
            raise ValueError(
                (
                    "Some instance IDs not found in dataset!"
                    f"\nMissing IDs:\n{' '.join(instance_ids - dataset_ids)}"
                )
            )
        missing_preds = instance_ids - set(predictions.keys())
        if missing_preds:
            print(f"Warning: Missing predictions for {len(missing_preds)} instance IDs.")
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
    completed_ids = set()
    for instance in dataset:
        if instance["instance_id"] not in prediction_ids:
            continue
        prediction = predictions[instance["instance_id"]]
        report_file = (
            RUN_INSTANCE_LOG_DIR
            / prediction["model_name_or_path"].replace("/", "__")
            / prediction["instance_id"]
            / "report.json"
        )
        if report_file.exists():
            completed_ids.add(instance["instance_id"])
    if completed_ids and exclude_completed:
        print(f"{len(completed_ids)} instances already run, skipping...")
        dataset = [i for i in dataset if i["instance_id"] not in completed_ids]
    dataset = [i for i in dataset if i["instance_id"] in prediction_ids]
    return dataset


def make_run_report(predictions, dataset, client, session_id):
    completed_ids = set()
    resolved_ids = set()
    error_ids = set()
    unstopped_containers = set()
    unremoved_images = set()
    test_specs = list(map(make_test_spec, dataset))
    for instance in dataset:
        instance_id = instance["instance_id"]
        prediction = predictions[instance_id]
        report_file = (
            RUN_INSTANCE_LOG_DIR
            / prediction["model_name_or_path"].replace("/", "__")
            / prediction["instance_id"]
            / "report.json"
        )
        if report_file.exists():
            completed_ids.add(instance_id)
            report = json.loads(report_file.read_text())
            if report[instance_id]["resolved"]:
                resolved_ids.add(instance_id)
        else:
            error_ids.add(instance_id)
    images = list_images(client)
    for spec in test_specs:
        image_name = spec.instance_image_key
        if image_name in images:
            unremoved_images.add(image_name)
    # docker list containers
    containers = client.containers.list(all=True)
    for container in containers:
        if session_id in container.name:
            unstopped_containers.add(container.name)
    print(f"Total instances: {len(dataset)}")
    print(f"Instances completed: {len(completed_ids)}")
    print(f"Instances resolved: {len(resolved_ids)}")
    print(f"Instances with errors: {len(error_ids)}")
    print(f"Instances still running: {len(unstopped_containers)}")
    print(f"Still existing images: {len(unremoved_images)}")
    report = {
        "total_instances": len(dataset),
        "completed_instances": len(completed_ids),
        "resolved_instances": len(resolved_ids),
        "error_instances": len(error_ids),
        "unstopped_instances": len(unstopped_containers),
        "completed_ids": sorted(list(completed_ids)),
        "resolved_ids": sorted(list(resolved_ids)),
        "error_ids": sorted(list(error_ids)),
        "unstopped_containers": sorted(list(unstopped_containers)),
        "unremoved_images": sorted(list(unremoved_images)),
    }
    report_file = Path(
        list(predictions.values())[0]["model_name_or_path"].replace("/", "__")
        + f".{session_id}"
        + ".json"
    )
    with open(report_file, "w") as f:
        print(json.dumps(report, indent=4), file=f)
    print(f"Report written to {report_file}")


def main(
    dataset_name,
    split,
    instance_ids,
    predictions_path,
    max_workers,
    force_rebuild,
    cache,
    clean,
    open_file_limit,
    session_id,
    timeout,
):
    if not session_id:
        session_id = str(uuid.uuid1())[:8]
    else:
        assert len(session_id) == 8, "Session ID must be 8 characters long."
    resource.setrlimit(resource.RLIMIT_NOFILE, (open_file_limit, open_file_limit))
    client = docker.from_env()
    with open(predictions_path, "r") as f:
        predictions = json.loads(f.read())
    predictions = {pred["instance_id"]: pred for pred in predictions}
    dataset = get_dataset_from_preds(dataset_name, split, instance_ids, predictions)
    full_dataset = get_dataset_from_preds(dataset_name, split, instance_ids, predictions, exclude_completed=False)
    existing_images = list_images(client)
    print(f"Running {len(dataset)} unevaluated instances...")
    if not dataset:
        print("No instances to run.")
    else:
        build_env_images(client, dataset, force_rebuild, max_workers)
        run_instances(predictions, dataset, cache, clean, force_rebuild, max_workers, session_id, timeout)
    clean_images(client, existing_images, cache, clean)
    make_run_report(predictions, full_dataset, client, session_id)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--dataset_name", default="princeton-nlp/SWE-bench", type=str, help="name of dataset")
    parser.add_argument("--split", type=str, default="test")
    parser.add_argument("--instance_ids", nargs="+", type=str, help="Instance IDs to run (space separated)")
    parser.add_argument("--predictions_path", type=str, help="Path to predictions file")
    parser.add_argument("--max_workers", type=int, default=4, help="Maximum number of workers")
    parser.add_argument("--open_file_limit", type=int, default=4096, help="Open file limit")
    parser.add_argument("--timeout", type=int, default=1_800, help="Timeout for running tests for each instance")
    parser.add_argument(
        "--force_rebuild", type=str2bool, default=False, help="Force rebuild of images"
    )
    parser.add_argument(
        "--cache",
        type=str,
        choices=["none", "base", "env", "instance"],
        help="Cache level",
        default="env",
    )
    # if clean is true then we remove all images that are above the cache level
    # if clean is false, we only remove images above the cache level if they don't already exist
    parser.add_argument(
        "--clean", type=str2bool, default=False, help="Clean images above cache level"
    )
    parser.add_argument("--session_id", type=str, help="Session ID")
    args = parser.parse_args()

    main(**vars(args))
