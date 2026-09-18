import docker
import re
import resource
import subprocess
import tempfile

from argparse import ArgumentParser
from contextlib import contextmanager
from pathlib import Path

from swebench.image_builder.image_spec import (
    canonical_image_ref,
    image_namespace_and_tag,
    make_image_spec,
)
from swebench.image_builder.docker_build import build_instance_images
from swebench.image_builder.docker_utils import list_images
from swebench.harness.utils import optional_str, str2bool
from swebench.task.publish import guard
from swebench.task.repo import load_dockerfiles, select_tasks, task_paths


def _is_github_ref(task_repo: str) -> bool:
    """Check if the task_repo is a GitHub reference (not a local path)."""
    if re.match(r"^https?://github\.com/", task_repo):
        return True
    if re.match(r"^[\w.-]+/[\w.-]+$", task_repo) and not Path(task_repo).is_dir():
        return True
    return False


def _github_ref_to_urls(task_repo: str) -> list[str]:
    """Convert a GitHub reference to clone URLs (SSH first, then HTTPS fallback)."""
    if re.match(r"^https?://github\.com/", task_repo):
        # Extract owner/repo from URL
        match = re.match(
            r"^https?://github\.com/([\w.-]+/[\w.-]+?)(?:\.git)?/?$", task_repo
        )
        if not match:
            return [task_repo.rstrip("/") + ".git"]
        owner_repo = match.group(1)
    else:
        owner_repo = task_repo
    return [
        f"git@github.com:{owner_repo}.git",
        f"https://github.com/{owner_repo}.git",
    ]


@contextmanager
def resolve_task_repo(task_repo: str):
    """
    Resolve a task repo reference to a local path.

    Accepts:
        - A local directory path (used directly)
        - A GitHub repo in "owner/repo" format
        - A GitHub URL like "https://github.com/owner/repo"

    Yields the local Path to the repo root.
    """
    if not _is_github_ref(task_repo):
        repo_path = Path(task_repo)
        if not repo_path.is_dir():
            raise FileNotFoundError(f"Local task repo not found: {task_repo}")
        yield repo_path
        return

    clone_urls = _github_ref_to_urls(task_repo)
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, clone_url in enumerate(clone_urls):
            print(f"Cloning task repo from {clone_url}...")
            result = subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, tmpdir],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                break
            if i < len(clone_urls) - 1:
                print(f"Clone failed, trying next URL...")
            else:
                raise RuntimeError(
                    f"Failed to clone task repo. Last error:\n{result.stderr}"
                )
        yield Path(tmpdir)


def filter_image_specs(
    image_specs: list,
    client: docker.DockerClient,
    force_rebuild: bool,
):
    """
    Filter the dataset to only include instances that need to be built.
    """
    existing_images = list_images(client)
    data_to_build = []

    for spec in image_specs:
        if force_rebuild:
            data_to_build.append(spec)
        elif spec.name not in existing_images:
            data_to_build.append(spec)

    return data_to_build


def main(
    task_repo,
    instance_ids,
    datasets,
    max_workers,
    force_rebuild,
    open_file_limit,
    namespace,
    tag,
    dry_run,
    split=None,
):
    """
    Build Docker images for the tasks in a task repo.

    Args:
        task_repo (str): Task repo reference — a local path, GitHub "owner/repo", or GitHub URL.
        instance_ids (list): Only these instances; without them, everything the repo publishes.
        datasets (list): Only tasks belonging to these datasets.
        max_workers (int): Number of workers for parallel processing.
        force_rebuild (bool): Whether to force rebuild all images.
        open_file_limit (int): Open file limit.
        namespace (str): Docker registry namespace.
        tag (str): Docker image tag.
        dry_run (bool): If True, create docker files and build contexts but don't build images.
        split (str | None): Only tasks in this split.
    """
    # Set open file limit
    resource.setrlimit(resource.RLIMIT_NOFILE, (open_file_limit, open_file_limit))
    client = docker.from_env(timeout=600)

    with resolve_task_repo(task_repo) as repo_path:
        guard(repo_path)
        dataset = select_tasks(repo_path, instance_ids, datasets)
        if split is not None:
            dataset = [instance for instance in dataset if instance.get("split") == split]
            if not dataset:
                raise ValueError(f"No tasks matched split {split!r}")
        ids = [i["instance_id"] for i in dataset]
        dockerfiles = load_dockerfiles(repo_path, ids)
        contexts = task_paths(repo_path, ids)
        image_specs = []
        for instance in dataset:
            inferred_namespace, _ = image_namespace_and_tag(instance["image"])
            image_specs.append(
                make_image_spec(
                    instance,
                    dockerfiles[instance["instance_id"]],
                    namespace if namespace is not None else inferred_namespace,
                    tag,
                    contexts.get(instance["instance_id"]),
                )
            )
        if namespace is None:
            mismatches = [
                f"{instance['instance_id']}: {spec.name} != {instance['image']}"
                for instance, spec in zip(dataset, image_specs)
                if spec.name != canonical_image_ref(instance["image"])
            ]
            if mismatches:
                raise ValueError(
                    "Default image names do not match task metadata: "
                    + ", ".join(mismatches)
                )
        image_specs = filter_image_specs(image_specs, client, force_rebuild)

        if len(image_specs) == 0:
            print("All images exist. Nothing left to build.")
            return 0

        if dry_run:
            print(
                f"DRY RUN MODE: Creating build contexts for {len(image_specs)} images (no actual builds will be performed)"
            )

        # Build images for remaining instances
        successful, failed = build_instance_images(
            client=client,
            image_specs=image_specs,
            force_rebuild=force_rebuild,
            max_workers=max_workers,
            dry_run=dry_run,
        )
    if dry_run:
        print(f"Successfully created build contexts for {len(successful)} images")
        if len(failed) > 0:
            print(f"Failed to create build contexts for {len(failed)} images")
    else:
        print(f"Successfully built {len(successful)} images")
        if len(failed) > 0:
            print(f"Failed to build {len(failed)} images")
            failed_ids = [
                payload[0].instance_id
                if isinstance(payload, tuple) and payload
                else str(payload)
                for payload in failed
            ]
            raise RuntimeError(
                f"{len(failed)} image build(s) failed: "
                + ", ".join(sorted(failed_ids))
            )
    return 0


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--instance_ids",
        nargs="+",
        type=str,
        help="Instance IDs to run (space separated)",
    )
    parser.add_argument(
        "--max_workers", type=int, default=4, help="Max workers for parallel processing"
    )
    parser.add_argument(
        "--force_rebuild", type=str2bool, default=False, help="Force rebuild images"
    )
    parser.add_argument(
        "--open_file_limit", type=int, default=65536, help="Open file limit"
    )
    parser.add_argument(
        "--namespace",
        type=optional_str,
        default=None,
        help="Namespace to use for the images (default: None)",
    )
    parser.add_argument(
        "--tag", type=str, default="latest", help="Tag to use for the images"
    )
    parser.add_argument(
        "--dry_run",
        type=str2bool,
        default=False,
        help="Create docker files and build contexts but don't build images",
    )
    parser.add_argument("--split", type=str, default=None, help="Only tasks in this split")
    parser.add_argument(
        "--task_repo",
        type=str,
        required=True,
        help="Task repo: local path, GitHub 'owner/repo', or 'https://github.com/owner/repo'",
    )
    args = parser.parse_args()
    main(**vars(args))
