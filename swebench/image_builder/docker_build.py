from __future__ import annotations

import docker
import docker.errors
import logging
import subprocess


from swebench.image_builder.constants import (
    IMAGE_BUILDER_LOG_DIR,
)
from swebench.image_builder.image_spec import (
    ImageSpec,
)
from swebench.harness.utils import run_threadpool
from swebench.logger import setup_logger, close_logger


class BuildImageError(Exception):
    def __init__(self, image_name, message, logger):
        super().__init__(message)
        self.super_str = super().__str__()
        self.image_name = image_name
        self.log_path = logger.log_file
        self.logger = logger

    def __str__(self):
        return (
            f"Error building image {self.image_name}: {self.super_str}\n"
            f"Check ({self.log_path}) for more information."
        )


def build_image(
    image_spec: ImageSpec,
    nocache: bool = False,
    dry_run: bool = False,
):
    """
    Builds a docker image using Docker Buildx with proper platform support.
    This fixes the "no specific platform was requested" warning.

    Args:
        image_spec (ImageSpec): Image specification containing dockerfile and metadata
        client (docker.DockerClient): Docker client (kept for compatibility)
        platform (str): Platform to build the image for (overridden by image_spec.platform)
        nocache (bool): Whether to use the cache when building
        dry_run (bool): If True, create docker files and build contexts but don't build images
        force_rebuild (bool): Build even when the target tag already exists
    """
    logger = setup_logger(
        image_spec.instance_id,
        IMAGE_BUILDER_LOG_DIR / image_spec.filesafe_name / "build_image.log",
    )
    logger.info(
        f"Building image {image_spec.name}\n"
        f"Using dockerfile:\n{image_spec.dockerfile}\n"
    )
    dockerfile_path = IMAGE_BUILDER_LOG_DIR / image_spec.filesafe_name / "Dockerfile"

    try:
        with open(dockerfile_path, "w") as f:
            f.write(image_spec.dockerfile)

        target_platform = image_spec.platform
        logger.info(
            f"Building docker image {image_spec.name} in {dockerfile_path} "
            f"with platform {target_platform} using Docker Buildx"
        )

        if not dry_run:
            cmd = [
                "docker",
                "buildx",
                "build",
                f"--platform={target_platform}",
                f"--tag={image_spec.name}",
                f"--file={dockerfile_path}",
                (
                    "--label=org.swebench.build-input-sha256="
                    f"{image_spec.build_input_digest}"
                ),
                "--progress=plain",
                "--load",
            ]

            if nocache:
                cmd.append("--no-cache")
            cmd.append(str(image_spec.context_dir or dockerfile_path.parent))

            logger.info(f"Executing: {' '.join(cmd)}")

            with open(logger.log_file, "a+") as log_file:
                process = subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                return_code = process.wait()

            if return_code == 0:
                logger.info("Image built successfully!")
            else:
                error_msg = f"Docker buildx failed with exit code {return_code}"
                logger.error(error_msg)
                raise BuildImageError(image_spec.name, error_msg, logger)
        else:
            logger.info("Build context created successfully!")
    except BuildImageError:
        raise
    except Exception as e:
        logger.error(f"Error building image {image_spec.name}: {e}")
        raise BuildImageError(image_spec.name, str(e), logger) from e
    finally:
        close_logger(logger)


def build_instance_images(
    client: docker.DockerClient,
    image_specs: list,
    force_rebuild: bool = False,
    max_workers: int = 4,
    dry_run: bool = False,
):
    """
    Builds the instance images required for the dataset if they do not already exist.

    Args:
        dataset (list): List of image specs or dataset to build images for
        client (docker.DockerClient): Docker client to use for building the images
        force_rebuild (bool): Whether to force rebuild the images even if they already exist
        max_workers (int): Maximum number of workers to use for building images
        dry_run (bool): If True, create docker files and build contexts but don't build images
    """
    successful, failed = list(), list()
    payloads = [
        (spec, client, None, False, dry_run, force_rebuild) for spec in image_specs
    ]
    successful, failed = run_threadpool(build_instance_image, payloads, max_workers)
    if len(failed) == 0:
        print("All instance images built successfully.")
    else:
        print(f"{len(failed)} instance images failed to build.")
    return successful, failed


def build_instance_image(
    image_spec: ImageSpec,
    client: docker.DockerClient,
    logger: logging.Logger | None,
    nocache: bool,
    dry_run: bool = False,
    force_rebuild: bool = False,
):
    """
    Builds the instance image for the given image spec if it does not already exist.

    Args:
        image_spec (ImageSpec): Image spec to build the instance image for
        client (docker.DockerClient): Docker client to use for building the image
        logger (logging.Logger): Logger to use for logging the build process
        nocache (bool): Whether to use the cache when building
        dry_run (bool): If True, create docker files and build contexts but don't build images
    """
    new_logger = False
    if logger is None:
        new_logger = True
        logger = setup_logger(image_spec.instance_id, add_stdout=True)

    image_exists = False
    if not dry_run:
        try:
            client.images.get(image_spec.name)
            image_exists = True
        except docker.errors.ImageNotFound:
            pass

    if force_rebuild or not image_exists:
        build_image(
            image_spec=image_spec,
            nocache=nocache,
            dry_run=dry_run,
        )
    else:
        logger.info(f"Image {image_spec.name} already exists, skipping build.")

    if new_logger:
        close_logger(logger)
