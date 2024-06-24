import json
import resource
import traceback
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import docker
from tqdm import tqdm

from swebench.harness.utils import str2bool
from swebench.harness.docker_utils import (
    get_session_id,
    list_images,
    clean_images,
)
from swebench.harness.docker_build import (
    build_instance_images,
)
from swebench.harness.dataset import load, make_test_spec


# def make_run_report(predictions, dataset, client, session_id):
#     completed_ids = set()
#     resolved_ids = set()
#     error_ids = set()
#     unstopped_containers = set()
#     unremoved_images = set()
#     test_specs = list(map(make_test_spec, dataset))
#     for instance in dataset:
#         instance_id = instance["instance_id"]
#         prediction = predictions[instance_id]
#         report_file = (
#             RUN_INSTANCE_LOG_DIR
#             / prediction["model_name_or_path"].replace("/", "__")
#             / prediction["instance_id"]
#             / "report.json"
#         )
#         if report_file.exists():
#             completed_ids.add(instance_id)
#             report = json.loads(report_file.read_text())
#             if report[instance_id]["resolved"]:
#                 resolved_ids.add(instance_id)
#         else:
#             error_ids.add(instance_id)
#     images = list_images(client)
#     for spec in test_specs:
#         image_name = spec.instance_image_key
#         if image_name in images:
#             unremoved_images.add(image_name)
#     # docker list containers
#     containers = client.containers.list(all=True)
#     for container in containers:
#         if session_id in container.name:
#             unstopped_containers.add(container.name)
#     print(f"Total instances: {len(dataset)}")
#     print(f"Instances completed: {len(completed_ids)}")
#     print(f"Instances resolved: {len(resolved_ids)}")
#     print(f"Instances with errors: {len(error_ids)}")
#     print(f"Instances still running: {len(unstopped_containers)}")
#     print(f"Still existing images: {len(unremoved_images)}")
#     report = {
#         "total_instances": len(dataset),
#         "completed_instances": len(completed_ids),
#         "resolved_instances": len(resolved_ids),
#         "error_instances": len(error_ids),
#         "unstopped_instances": len(unstopped_containers),
#         "completed_ids": sorted(list(completed_ids)),
#         "resolved_ids": sorted(list(resolved_ids)),
#         "error_ids": sorted(list(error_ids)),
#         "unstopped_containers": sorted(list(unstopped_containers)),
#         "unremoved_images": sorted(list(unremoved_images)),
#     }
#     report_file = Path(
#         list(predictions.values())[0]["model_name_or_path"].replace("/", "__")
#         + f".{session_id}"
#         + ".json"
#     )
#     with open(report_file, "w") as f:
#         print(json.dumps(report, indent=4), file=f)
#     print(f"Report written to {report_file}")


def filter_dataset_to_build(dataset, instance_ids, client, force_rebuild):
    existing_images = list_images(client)
    data_to_build = []
    not_in_dataset = set(instance_ids).difference(set([instance["instance_id"] for instance in dataset]))
    if not_in_dataset:
        raise ValueError(f"Instance IDs not found in dataset: {not_in_dataset}")
    for instance in dataset:
        if instance["instance_id"] not in instance_ids:
            continue
        spec = make_test_spec(instance)
        if force_rebuild:
            data_to_build.append(instance)
        elif spec.instance_image_key not in existing_images:
            data_to_build.append(instance)
    return data_to_build


def main(
    instance_ids,
    max_workers,
    force_rebuild,
    open_file_limit,
):
    resource.setrlimit(resource.RLIMIT_NOFILE, (open_file_limit, open_file_limit))
    client = docker.from_env()
    dataset = load()
    dataset = filter_dataset_to_build(dataset, instance_ids, client, force_rebuild)
    successful, failed = build_instance_images(
        dataset=dataset,
        client=client,
        force_rebuild=force_rebuild,
        max_workers=max_workers,
    )
    print(f"Successfully built {len(successful)} images")
    print(f"Failed to build {len(failed)} images")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--instance_ids", nargs="+", type=str, help="Instance IDs to run (space separated)")
    parser.add_argument("--max_workers", type=int, default=4, help="Max workers for parallel processing")
    parser.add_argument("--force_rebuild", type=str2bool, default=False, help="Force rebuild images")
    parser.add_argument("--open_file_limit", type=int, default=8192, help="Open file limit")
    args = parser.parse_args()
    main(**vars(args))
