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
    list_images,
    clean_images,
)
from swebench.harness.docker_build import (
    build_instance_images,
)
from swebench.harness.dataset import load, make_test_spec


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
