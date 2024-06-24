import logging
import re
import traceback
import docker
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from swebench.harness.constants import MAP_VERSION_TO_INSTALL
from swebench.harness.dataset import make_test_spec
from swebench.harness.docker_utils import cleanup_image, list_images, cleanup_container

ansi_escape = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
INSTANCE_IMAGE_BUILD_DIR = Path("image_build_logs/instances")
ENV_IMAGE_BUILD_DIR = Path("image_build_logs/env")
BASE_IMAGE_BUILD_DIR = Path("image_build_logs/base")


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
    log_file.parent.mkdir(parents=True, exist_ok=True)
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


def build_image(
    image_name, setup_scripts, dockerfile, platform, client, build_dir, nocache=False
):
    logger = setup_logger(image_name, build_dir / "build_image.log")
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
        build_image(
            image_name=image_name,
            setup_scripts={},
            dockerfile=dockerfile,
            platform=platform,
            client=client,
            build_dir=BASE_IMAGE_BUILD_DIR / image_name.replace(":", "__"),
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


def build_instance_images(dataset, client, force_rebuild=False, max_workers=4, chunk_size=100):
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
                    None,  # logger is created in build_instance_image, don't make loggers before you need them
                    False,
                    force_rebuild,
                ): test_spec.instance_id
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
    build_dir = INSTANCE_IMAGE_BUILD_DIR / test_spec.instance_image_key.replace(":", "__")
    if logger is None:
        logger = setup_logger(test_spec.instance_id, build_dir / "prepare_image.log")
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

