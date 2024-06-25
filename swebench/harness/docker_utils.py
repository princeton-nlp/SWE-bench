import docker
import hashlib
import os
import secrets
import signal
import string
import tarfile
import threading
import time
import traceback
from pathlib import Path

from docker.models.containers import Container

HEREDOC_DELIMITER = "EOF_1399519320"  # different from dataset HEREDOC_DELIMITERs!


def copy_to_container(container: Container, src: Path, dst: Path):
    if os.path.dirname(dst) == "":
        raise ValueError(
            f"Destination path parent directory cannot be empty!, dst: {dst}"
        )
    # temporary tar file
    tar_path = src.with_suffix(".tar")
    with tarfile.open(tar_path, "w") as tar:
        tar.add(src, arcname=src.name)

    # get bytes for put_archive cmd
    with open(tar_path, "rb") as tar_file:
        data = tar_file.read()

    # Make directory if necessary
    container.exec_run(f"mkdir -p {dst.parent}")

    container.put_archive(os.path.dirname(dst), data)
    container.exec_run(f"tar -xf {dst}.tar -C {dst.parent}")

    # clean up in locally and in container
    tar_path.unlink()
    container.exec_run(f"rm {dst}.tar")


def write_to_container(container: Container, data: str, dst: Path):
    # echo with heredoc to file
    command = f"cat <<'{HEREDOC_DELIMITER}' > {dst}\n{data}\n{HEREDOC_DELIMITER}"
    container.exec_run(command)


def cleanup_image(client, image_id, rm_image, logger=None):
    if not logger:
        log_info = print
        log_error = print
        raise_error = True
    elif logger == "quiet":
        log_info = lambda x: None
        log_error = lambda x: None
        raise_error = True
    else:
        log_error = logger.info
        log_info = logger.info
        raise_error = False
    if rm_image:
        try:
            log_info(f"Attempting to remove image {image_id}...")
            client.images.remove(image_id, force=True)
            log_info(f"Image {image_id} removed.")
        except Exception as e:
            if raise_error:
                raise e
            log_error(
                f"Failed to remove image {image_id}: {e}\n" f"{traceback.format_exc()}"
            )


def cleanup_container(client, container, logger):
    if not container:
        return

    container_id = container.id

    if not logger:
        log_error = print
        log_info = print
        raise_error = True
    elif logger == "quiet":
        log_info = lambda x: None
        log_error = lambda x: None
        raise_error = True
    else:
        log_error = logger.info
        log_info = logger.info
        raise_error = False

    try:
        if container:
            log_info(f"Attempting to stop container {container.name}...")
            container.stop(timeout=15)
    except Exception as e:
        log_error(
            f"Failed to stop container {container.name}: {e}. Trying to forcefully kill..."
        )
        try:
            container_info = client.api.inspect_container(container_id)
            pid = container_info["State"].get("Pid", 0)
            if pid > 0:
                log_info(
                    f"Forcefully killing container {container.name} with PID {pid}..."
                )
                os.kill(pid, signal.SIGKILL)
            else:
                log_error(f"PID for container {container.name}: {pid} - not killing.")
        except Exception as e2:
            if raise_error:
                raise e2
            log_error(
                f"Failed to forcefully kill container {container.name}: {e2}\n"
                f"{traceback.format_exc()}"
            )
    try:
        log_info(f"Attempting to remove container {container.name}...")
        container.remove(force=True)
        log_info(f"Container {container.name} removed.")
    except Exception as e:
        if raise_error:
            raise e
        log_error(
            f"Failed to remove container {container.name}: {e}\n"
            f"{traceback.format_exc()}"
        )


def exec_run_with_timeout(container, cmd, timeout=60):
    exec_result = None
    exec_id = None
    exception = None

    def run_command():
        nonlocal exec_result, exec_id, exception
        try:
            exec_id = container.client.api.exec_create(container.id, cmd)["Id"]
            exec_result = container.client.api.exec_start(exec_id)
        except Exception as e:
            exception = e

    thread = threading.Thread(target=run_command)
    thread.start()
    thread.join(timeout)

    if exception:
        raise exception

    if thread.is_alive():
        raise TimeoutError(f"Command '{cmd}' timed out after {timeout} seconds")

    return exec_result


def find_dependent_images(client, image_name):
    """
    Find all images that are built upon `image_name` image
    """
    dependent_images = []

    # Get all local images
    all_images = client.images.list()

    # Get the ID of the base image
    try:
        base_image = client.images.get(image_name)
        base_image_id = base_image.id
    except docker.errors.ImageNotFound:
        print(f"Base image {image_name} not found.")
        return []

    for image in all_images:
        # Skip the base image itself
        if image.id == base_image_id:
            continue

        # Check if the base image is in this image's history
        history = image.history()
        for layer in history:
            if layer['Id'] == base_image_id:
                # If found, add this image to the dependent images list
                tags = image.tags
                dependent_images.append(tags[0] if tags else image.id)
                break

    return dependent_images


def list_images(client):
    # don't use this in multi-threaded context
    return {tag for i in client.images.list(all=True) for tag in i.tags}


def clean_images(client, prior_images, cache, clean):
    images = list_images(client)
    removed = 0
    print(f"Cleaning cached images...")
    for image_name in images:
        if should_remove(image_name, cache, clean, prior_images):
            try:
                cleanup_image(client, image_name, True, "quiet")
                removed += 1
            except Exception as e:
                print(f"Error removing image {image_name}: {e}")
                continue
    print(f"Removed {removed} images.")


def should_remove(image_name, cache, clean, prior_images):
    """
    Determine if an image should be removed based on cache level and clean flag.
    """
    existed_before = image_name in prior_images
    if image_name.startswith("sweb.base"):
        if cache in {"none"} and (clean or not existed_before):
            return True
    elif image_name.startswith("sweb.env"):
        if cache in {"none", "base"} and (clean or not existed_before):
            return True
    elif image_name.startswith("sweb.eval"):
        if cache in {"none", "base", "env"} and (clean or not existed_before):
            return True
    return False
