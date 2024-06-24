import os
import signal
import string
import time
import hashlib
import secrets
import tarfile
import traceback
import threading
import logging
import re
import docker
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from docker.models.containers import Container
from swebench.harness.constants import MAP_VERSION_TO_INSTALL
from swebench.harness.dataset import make_test_spec


ansi_escape = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
INSTANCE_IMAGE_BUILD_DIR = Path("image_build_logs/instances")
ENV_IMAGE_BUILD_DIR = Path("image_build_logs/env")
BASE_IMAGE_BUILD_DIR = Path("image_build_logs/base")
HEREDOC_DELIMITER = "EOF_1399519320"  # different from dataset HEREDOC_DELIMITERs!


class BuildImageError(Exception):
    def __init__(self, instance_id, message, logger):
        super().__init__(message)
        self.instance_id = instance_id
        self.log_path = logger.log_file
        self.logger = logger

    def __str__(self):
        log_msg = " ".join(traceback.TracebackException.from_exception(self).format())
        self.logger.error(log_msg)
        return (
            f"{self.instance_id}: {super().__str__()}\n"
            f"Check ({self.log_path}) for more information."
        )


def setup_logger(instance_id, log_file: Path, mode="w"):
    logger = logging.getLogger(f"{instance_id}.{log_file.name}")
    handler = logging.FileHandler(log_file, mode=mode)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    setattr(logger, "log_file", log_file)
    return logger


def close_logger(logger):
    # To avoid too many open files
    for handler in logger.handlers:
        handler.close()
        logger.removeHandler(handler)


def get_session_id(length=8):
    """
    Generates a random string of specified length.

    Parameters:
    length (int): The length of the random string. Default is 8.

    Returns:
    str: The generated random string.

    Raises:
    ValueError: If length is not a positive integer or no character set is selected.
    """
    if not isinstance(length, int) or length <= 0:
        raise ValueError("Length must be a positive integer.")

    characters = ""
    characters += string.ascii_uppercase
    characters += string.ascii_lowercase
    characters += string.digits
    if not characters:
        raise ValueError(
            "At least one character set (uppercase, lowercase, digits) must be enabled."
        )
    # Create a high-resolution timestamp seed
    timestamp = time.time_ns()
    timestamp_bytes = str(timestamp).encode("utf-8")
    seed = hashlib.sha256(timestamp_bytes).digest()
    random_gen = secrets.SystemRandom(int.from_bytes(seed, "big"))
    random_string = "".join(random_gen.choice(characters) for _ in range(length))
    return random_string


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


def list_images(client):
    # don't use this in multi-threaded context
    return {tag for i in client.images.list(all=True) for tag in i.tags}


def build_image(
    image_name, setup_scripts, dockerfile, platform, client, build_dir, nocache=False
):
    build_dir.mkdir(parents=True, exist_ok=True)
    log_file = build_dir / "build_image.log"
    logger = setup_logger(image_name, log_file)
    logger.info(
        f"Building image {image_name}\n"
        f"Using dockerfile:\n{dockerfile}\n"
        f"Adding ({len(setup_scripts)}) setup scripts to image build repo"
    )
    for setup_script_name, setup_script in setup_scripts.items():
        logger.info(f"[SETUP SCRIPT] {setup_script_name}:\n{setup_script}")
    try:
        for setup_script_name, setup_script in setup_scripts.items():
            setup_script_path = build_dir / setup_script_name
            with open(setup_script_path, "w") as f:
                f.write(setup_script)
            if setup_script_name not in dockerfile:
                logger.warning(
                    f"Setup script {setup_script_name} may not be used in Dockerfile"
                )

        dockerfile_path = build_dir / "Dockerfile"
        with open(dockerfile_path, "w") as f:
            f.write(dockerfile)

        logger.info(
            f"Building docker image {image_name} in {build_dir} with platform {platform}"
        )
        response = client.api.build(
            path=str(build_dir),
            tag=image_name,
            rm=True,
            forcerm=True,
            decode=True,
            platform=platform,
            nocache=nocache,
        )
        buildlog = ""
        for chunk in response:
            if "stream" in chunk:
                chunk_stream = ansi_escape.sub("", chunk["stream"])
                logger.info(chunk_stream.strip())
                buildlog += chunk_stream
            elif "errorDetail" in chunk:
                logger.error(
                    f"Error: {ansi_escape.sub('', chunk['errorDetail']['message'])}"
                )
                raise docker.errors.BuildError(
                    chunk["errorDetail"]["message"], buildlog
                )
        logger.info("Image built successfully!")
    except docker.errors.BuildError as e:
        logger.error(f"docker.errors.BuildError during {image_name}: {e}")
        raise BuildImageError(image_name, str(e), logger) from e
    except Exception as e:
        logger.error(f"Error building image {image_name}: {e}")
        raise BuildImageError(image_name, str(e), logger) from e
    finally:
        close_logger(logger)  # functions that create loggers should close them


def build_base_images(client, test_specs):
    base_images = {
        x.base_image_key: (x.base_dockerfile, x.platform) for x in test_specs
    }
    for image_name, (dockerfile, platform) in base_images.items():
        print(f"Building base image ({image_name})")
        log_dir = BASE_IMAGE_BUILD_DIR / image_name.replace(":", "__")
        log_dir.mkdir(parents=True, exist_ok=True)
        build_image(
            image_name=image_name,
            setup_scripts={},
            dockerfile=dockerfile,
            platform=platform,
            client=client,
            build_dir=log_dir,
        )
    print("Base images built successfully.")


def get_env_configs(test_specs, force_rebuild, client):
    all_image_names = list_images(client)
    image_scripts = dict()
    for test_spec in test_specs:
        image_key = test_spec.env_image_key
        dockerfile = test_spec.env_dockerfile
        if image_key not in all_image_names or force_rebuild:
            if image_key in all_image_names and force_rebuild:
                cleanup_image(client, image_key, True, "quiet")
            image_scripts[image_key] = {
                "setup_script": test_spec.setup_env_script,
                "dockerfile": dockerfile,
                "platform": test_spec.platform,
            }
    return image_scripts


def build_env_images(dataset, client, force_rebuild=False, max_workers=4):
    test_specs = list(map(make_test_spec, dataset))
    image_configs = get_env_configs(test_specs, force_rebuild, client)
    all_image_names = list_images(client)
    base_image_names = {x.base_image_key for x in test_specs}
    if not all(
        base_image_name in all_image_names for base_image_name in base_image_names
    ):
        build_base_images(client, test_specs)
    elif force_rebuild:
        print("Rebuilding base image(s)")
        for base_image_name in base_image_names:
            if base_image_name in all_image_names:
                cleanup_image(client, base_image_name, True, "quiet")
        build_base_images(client, test_specs)
    else:
        print(f"Base image(s) {base_image_names} already exist, skipping build.")

    configs_to_build = [
        (image_name, scripts)
        for image_name, scripts in image_configs.items()
        if image_name not in all_image_names or force_rebuild
    ]

    print(f"Total environment images to build: {len(configs_to_build)}")
    all_successful = True
    with tqdm(
        total=len(configs_to_build), smoothing=0, desc="Building environment images"
    ) as pbar:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    build_image,
                    image_name,
                    {"setup_env.sh": config["setup_script"]},
                    config["dockerfile"],
                    config["platform"],
                    client,
                    ENV_IMAGE_BUILD_DIR / image_name.replace(":", "__"),
                ): image_name
                for image_name, config in configs_to_build
            }
            for future in as_completed(futures):
                pbar.update(1)
                try:
                    future.result()
                except BuildImageError as e:
                    print(f"BuildImageError {e.instance_id}")
                    traceback.print_exc()
                    all_successful = False
                    continue
                except Exception as e:
                    print(f"Error building image")
                    traceback.print_exc()
                    all_successful = False
                    continue
    if all_successful:
        print("All environment images built successfully.")
    else:
        # raise Exception("Error building environment images.")
        print("Error building environment images.")


def build_instance_images(dataset, client, force_rebuild=False, max_workers=4):
    test_specs = list(map(make_test_spec, dataset))
    all_image_names = list_images(client)
    env_image_names = {x.env_image_key for x in test_specs}
    if not all(env_image_name in all_image_names for env_image_name in env_image_names):
        build_env_images(dataset, client, force_rebuild, max_workers)
    elif force_rebuild:
        print("Rebuilding environment image(s)")
        for env_image_name in env_image_names:
            if env_image_name in all_image_names:
                cleanup_image(client, env_image_name, True, "quiet")
        build_env_images(dataset, client, force_rebuild, max_workers)
    else:
        print(f"Environment image(s) {env_image_names} already exist, skipping build.")

    print(f"Building instance images for {len(test_specs)} instances")
    all_successful = True
    with tqdm(
        total=len(test_specs), smoothing=0, desc="Building instance images"
    ) as pbar:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    build_instance_image,
                    test_spec,
                    client,
                    setup_logger(test_spec.instance_id, Path("/dev/null")),
                    False,
                    force_rebuild,
                ): test_spec
                for test_spec in test_specs
            }
            for future in as_completed(futures):
                pbar.update(1)
                try:
                    future.result()
                except BuildImageError as e:
                    print(f"BuildImageError {e.instance_id}")
                    traceback.print_exc()
                    all_successful = False
                    continue
                except Exception as e:
                    print(f"Error building image")
                    traceback.print_exc()
                    all_successful = False
                    continue
    if all_successful:
        print("All instance images built successfully.")
    else:
        # raise Exception("Error building instance images.")
        print("Error building instance images.")


def build_instance_image(test_spec, client, logger, nocache, force_rebuild=False):
    image_name = test_spec.instance_image_key
    env_image_name = test_spec.env_image_key
    dockerfile = test_spec.instance_dockerfile
    try:
        client.images.get(env_image_name)
    except docker.errors.ImageNotFound as e:
        raise BuildImageError(
            test_spec.instance_id,
            f"Environment image {env_image_name} not found for {test_spec.instance_id}",
            logger,
        ) from e
    logger.info(
        f"Environment image {env_image_name} found for {test_spec.instance_id}\n"
        f"Building instance image {image_name} for {test_spec.instance_id}"
    )
    image_exists = False
    try:
        client.images.get(image_name)
        image_exists = True
    except docker.errors.ImageNotFound:
        pass
    if image_exists and force_rebuild:
        cleanup_image(client, image_name, True, "quiet")
        image_exists = False
    build_dir = INSTANCE_IMAGE_BUILD_DIR / image_name.replace(":", "__")
    if not image_exists:
        build_image(
            image_name=image_name,
            setup_scripts={
                "setup_repo.sh": test_spec.install_repo_script,
                "eval.sh": test_spec.eval_script,
            },
            dockerfile=dockerfile,
            platform=test_spec.platform,
            client=client,
            build_dir=build_dir,
            nocache=nocache,
        )
    else:
        logger.info(f"Image {image_name} already exists, skipping build.")


def build_container(
    test_spec, client, session_id, logger, nocache, force_rebuild=False
):
    build_instance_image(test_spec, client, logger, nocache, force_rebuild)
    container = None
    try:
        config = MAP_VERSION_TO_INSTALL[test_spec.repo][test_spec.version]
        user = "root" if not config.get("execute_test_as_nonroot", False) else "nonroot"
        # user = "root"
        nano_cpus = config.get("nano_cpus")
        logger.info(f"Creating container for {test_spec.instance_id}...")
        container = client.containers.create(
            image=test_spec.instance_image_key,
            name=test_spec.get_instance_container_name(session_id),
            user=user,
            detach=True,
            command="tail -f /dev/null",
            nano_cpus=nano_cpus,
            platform=test_spec.platform,
        )
        logger.info(f"Container for {test_spec.instance_id} created: {container.id}")
        return container
    except Exception as e:
        logger.error(f"Error creating container for {test_spec.instance_id}: {e}")
        logger.info(traceback.format_exc())
        cleanup_container(client, container, logger)
        raise BuildImageError(test_spec.instance_id, str(e), logger) from e
