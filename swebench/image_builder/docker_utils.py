from __future__ import annotations

import docker
import docker.errors
import traceback

from swebench.utils import generate_heredoc_delimiter, _get_log_objects
from swebench.image_builder.constants import REPO_BASE_COMMIT_BRANCH


def remove_image(client, image_id, logger=None):
    """
    Remove a Docker image by ID.

    Args:
        client (docker.DockerClient): Docker client.
        image_id (str): Image ID.
        logger (logging.Logger): Logger to use for output. If None, print to stdout.
    """
    log_info, log_error, raise_error = _get_log_objects(logger)
    try:
        log_info(f"Attempting to remove image {image_id}...")
        client.images.remove(image_id, force=True)
        log_info(f"Image {image_id} removed.")
    except (docker.errors.ImageNotFound, docker.errors.NotFound):
        log_info(f"Image {image_id} not found, removing has no effect.")
    except Exception as e:
        if raise_error:
            raise e
        log_error(f"Failed to remove image {image_id}: {e}\n{traceback.format_exc()}")


def list_images(client: docker.DockerClient):
    """
    List all images from the Docker client.
    """
    # don't use this in multi-threaded context
    return {tag for i in client.images.list(all=True) for tag in i.tags}


def make_heredoc_run_command(commands: list[str]) -> str:
    """
    Create a heredoc-style RUN command from a list of shell commands.

    Args:
        commands: List of shell commands to execute
    Returns:
        A single heredoc-style RUN command string
    """
    if not commands:
        return ""

    heredoc_content = "\n".join(["#!/bin/bash", "set -euxo pipefail", *commands])
    delimiter = generate_heredoc_delimiter(heredoc_content)
    return f"RUN <<{delimiter}\n{heredoc_content}\n{delimiter}\n"


def git_clone_timesafe(repo: str, base_commit: str, workdir: str) -> list[str]:
    """
    Generate a list of shell commands to clone a Git repository and remove references to future information.
    """
    branch = REPO_BASE_COMMIT_BRANCH.get(repo, {}).get(base_commit, "")
    branch = f"--branch {branch}" if branch else ""
    return [
        f"git clone -o origin {branch} --single-branch https://github.com/{repo} {workdir}",
        f"chmod -R 777 {workdir}",  # So nonroot user can run tests
        f"cd {workdir}",
        f"git reset --hard {base_commit}",
        "git remote remove origin",
        f"TARGET_TIMESTAMP=$(git show -s --format=%ct {base_commit})",
        'git tag -l | while read tag; do TAG_COMMIT=$(git rev-list -n 1 "$tag"); TAG_TIME=$(git show -s --format=%ct "$TAG_COMMIT"); if [[ $TAG_TIME -gt $TARGET_TIMESTAMP ]]; then git tag -d "$tag"; fi; done',
        "git reflog expire --expire=now --all",
        "git gc --prune=now --aggressive",
        "AFTER_TIMESTAMP=$((TARGET_TIMESTAMP + 1))",
        'COMMIT_COUNT=$(git log --oneline --all --after="@$AFTER_TIMESTAMP" | wc -l)',
        '[ "$COMMIT_COUNT" -eq 0 ] || exit 1',
        "cd - || true",
    ]
