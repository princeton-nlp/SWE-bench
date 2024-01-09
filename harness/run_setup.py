import argparse
import json
import logging
import os
import shutil
from multiprocessing import Pool
from os.path import join as pjoin
from typing import Dict

from constants import KEY_INSTANCE_ID, MAP_VERSION_TO_INSTALL
from context_manager import ExecWrapper
from utils import clone_repo, get_environment_yml, get_requirements

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("run_setup")


def create_conda_env(
    repo_full: str, version: str, repo_path: str, env_name: str, instance: Dict
):
    """
    Create a conda environment for the repo.

    Args:
        repo_full: full name of the repo, in the form "user/repo".
        version: version of the repo.
        repo_path: the cloned repo path on disk.
        env_name: name of the conda environment to create.
        instance: Dict containing task instance.
    """
    exec_wrapper = ExecWrapper(
        subprocess_args={
            "check": True,
            "shell": False,
            "capture_output": True,
            "text": True,
        }
    )

    # (1) figure out which conda to use
    conda_bin_path = os.getenv("CONDA_EXE")  # for calling conda
    activate_path = pjoin(os.path.dirname(conda_bin_path), "activate")  # for activate

    # (2) get install information
    repo_map_version_to_install = MAP_VERSION_TO_INSTALL[repo_full]
    # dict with key "python", "packages", "pip_packages", "install"
    install = repo_map_version_to_install[version]

    # (3) do the real work: consider different project setups
    pkgs = install["packages"] if "packages" in install else ""
    python_version = install["python"]
    # create a temp dir to save setup temp files
    temp_dir = pjoin(repo_path, "setup_temp")
    os.makedirs(temp_dir, exist_ok=True)

    if pkgs == "requirements.txt":
        # create environment
        cmd = f"{conda_bin_path} create -n {env_name} python={python_version} -y"
        logger.info(f"Creating environment {env_name}; Command: {cmd}")
        exec_wrapper(cmd.split(" "))
        # install dependencies
        path_to_reqs = get_requirements(instance, temp_dir)
        cmd = f"source {activate_path} {env_name} && echo 'activate successful' && pip install -r {path_to_reqs}"
        logger.info(f"Installing dependencies for {env_name}; Command: {cmd}")
        exec_wrapper(cmd, shell=True)
        os.remove(path_to_reqs)

    elif pkgs == "environment.yml":
        # create environment from yml
        path_to_reqs = get_environment_yml(instance, env_name, temp_dir)
        if "no_use_env" in install and install["no_use_env"]:
            # `conda create` based installation
            cmd = f"{conda_bin_path} create -c conda-forge -n {env_name} python={python_version} -y"
            logger.info(f"Creating environment {env_name}; Command: {cmd}")
            exec_wrapper(cmd.split(" "))
            # Install dependencies
            cmd = f"{conda_bin_path} env update -f {path_to_reqs}"
            logger.info(f"Installing dependencies for {env_name}; Command: {cmd}")
            exec_wrapper(cmd.split(" "))
        else:
            # `conda env create` based installation
            cmd = f"{conda_bin_path} env create --file {path_to_reqs}"
            logger.info(f"Creating environment {env_name}; Command: {cmd}")
            exec_wrapper(cmd.split(" "))
        # Remove environment.yml
        os.remove(path_to_reqs)

    else:
        # Create environment + install dependencies
        cmd = f"{conda_bin_path} create -n {env_name} python={python_version} {pkgs} -y"
        logger.info(f"Creating environment {env_name}; Command: {cmd}")
        exec_wrapper(cmd.split(" "))

    # Install additional packages if specified
    if "pip_packages" in install:
        pip_packages = install["pip_packages"]
        cmd = f"source {activate_path} {env_name} && pip install {pip_packages}"
        logger.info(f"Installing pip packages for {env_name}; Command: {cmd}")
        exec_wrapper(cmd.split(" "))


def create_fresh_dir(dir_name: str):
    if os.path.exists(dir_name):
        shutil.rmtree(dir_name)
    os.makedirs(dir_name)


def load_task_instances(swe_bench_tasks: str):
    if not os.path.exists(swe_bench_tasks):
        raise ValueError("--swe_bench_tasks does not exist")
    tasks = json.load(open(os.path.abspath(swe_bench_tasks)))
    if not isinstance(tasks, list):
        raise ValueError(f"{swe_bench_tasks} must contain an array of tasks")
    return tasks


def main(
    swe_bench_tasks: str,
    log_dir: str,
    testbed: str,
    result_dir: str,
    num_processes: int = -1,
):
    """
    Runs set up for each repo/version combination.

    Args:
        swe_bench_tasks (str): Path to the SWE-bench tasks file.
        log_dir (str): Path to the directory where logs will be saved.
        testbed (str): Path to the directory where testbeds will be saved.
        result_dir (str): Path to the directory where results are stored.
    Raises:
        ValueError: If log_dir is not a directory, testbed is not a directory, or swe_bench_tasks does not exist.
    """
    # Validate arguments
    create_fresh_dir(log_dir)
    create_fresh_dir(testbed)
    create_fresh_dir(result_dir)
    tasks = load_task_instances(swe_bench_tasks)
    # map instance_id to the actual task instance Dict
    tasks_map = {t[KEY_INSTANCE_ID]: t for t in tasks}
    # map instance_id to setup information
    setup_map = {i: {} for i in tasks_map}

    # iterates all tasks, decide the path for their testbed folder, and save this path to task_map
    for instance_id, task in tasks_map.items():
        repo_full = task["repo"]  # "astropy/astropy"
        repo_short = instance_id.rsplit("-", 1)[0]  # "astropy"
        version = task["version"]  # "4.2"
        # name for both conda env and testbed folder
        env_name = f"{repo_short}__{version}"
        repo_path = pjoin(testbed, repo_short, env_name)
        # keys in setup_map
        setup_map["repo_path"] = repo_path
        setup_map["env_name"] = env_name
        if os.path.exists(repo_path):
            # repo_path has already been setup before, skip
            continue

        logger.info(f"======= Start setting up for {repo_full} {version} =======")
        clone_repo(repo_full, repo_path)
        logger.info(f"Cloned {repo_full} to {repo_path}")
        create_conda_env(repo_full, version, repo_path, env_name, task)
        logger.info(f"Created conda environment {env_name} for {repo_full}{version}")

    # Done with the actual work. We should dump the two maps to disk,
    # so other clients can use them to find locations of the setup
    setup_map_path = pjoin(result_dir, "setup_map.json")
    tasks_map_path = pjoin(result_dir, "tasks_map.json")
    with open(setup_map_path, "w") as f:
        json.dump(setup_map, f)
    with open(tasks_map_path, "w") as f:
        json.dump(tasks_map, f)

    print("Done with setup.")
    print(f"setup_map is saved to {setup_map_path}")
    print(f"tasks_map is saved to {tasks_map_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log_dir", type=str, help="Path to log directory", required=True
    )
    parser.add_argument(
        "--swe_bench_tasks",
        type=str,
        help="Path to SWE-bench task instances file",
        required=True,
    )
    parser.add_argument(
        "--testbed", type=str, help="Path to testbed directory", required=True
    )
    parser.add_argument(
        "--result_dir",
        type=str,
        help="Directory to store the setup result maps",
        required=True,
    )
    parser.add_argument(
        "--num_processes",
        type=int,
        help="(Optional) Number of processes to use.",
        default=-1,
    )
    args = parser.parse_args()
    logger.propagate = args.verbose
    main(**vars(args))
