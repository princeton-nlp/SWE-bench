import argparse
import json
import logging
import os
import shutil
import pandas as pd
from multiprocessing import Pool
from os.path import join as pjoin
from typing import Dict, Optional, Tuple, List

from constants import (
    KEY_INSTANCE_ID,
    MAP_REPO_TO_INSTALL,
    MAP_VERSION_TO_INSTALL,
    MAP_REPO_TO_TEST_FRAMEWORK,
)
from context_manager import ExecWrapper
from utils import (
    clone_repo,
    get_conda_env_names,
    get_environment_yml,
    get_requirements,
    get_test_directives,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("run_setup")


def create_fresh_dir(dir_name: str):
    if os.path.exists(dir_name):
        shutil.rmtree(dir_name)
    os.makedirs(dir_name)


def create_if_not_exist(dir_name: str):
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)


def remove_conda_env_and_dir(env_name: str):
    """
    Completely remove conda env and its folder on disk.
    """
    exec_wrapper = ExecWrapper(
        subprocess_args={
            "check": True,
            "shell": False,
            "capture_output": True,
            "text": True,
        }
    )
    # figure out which conda to use
    conda_bin_path = os.getenv("CONDA_EXE")  # for calling conda
    conda_bin_dir = os.path.dirname(conda_bin_path)
    conda_env_dir = pjoin(os.path.dirname(conda_bin_dir), "envs")

    # remove env with conda command
    existing_env_list = get_conda_env_names(conda_bin_path)
    if env_name in existing_env_list:
        # env_name has already been created.
        cmd = f"{conda_bin_path} remove -n {env_name} --all -y"
        logger.info(f"[{env_name}] Removing old conda env {env_name}")
        exec_wrapper(cmd.split(" "))

    # remove potential dangling env folder
    env_dir = pjoin(conda_env_dir, env_name)
    if os.path.exists(env_dir):
        logger.info(f"[{env_name}] Removing dangling conda env folder {env_dir}")
        shutil.rmtree(env_dir)


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

    # figure out which conda to use
    conda_bin_path = os.getenv("CONDA_EXE")  # for calling conda
    conda_bin_dir = os.path.dirname(conda_bin_path)
    activate_path = pjoin(conda_bin_dir, "activate")  # for activate
    deactivate_path = pjoin(conda_bin_dir, "deactivate")  # for deactivate

    # if an old env with the same name exists, remove it
    remove_conda_env_and_dir(env_name)

    # (1) Run any top-level installation commands if provided (currently empty)
    # TODO: ideally this should only be done once per repo; but now
    # is done once per version, which means there are duplicated execs
    if repo_full in MAP_REPO_TO_INSTALL:
        install_cmd = MAP_REPO_TO_INSTALL[repo_full]
        logger.info(
            f"[{env_name}] Running custom install command for {repo_full}: {install_cmd}"
        )
        exec_wrapper(install_cmd, shell=True)

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
        logger.info(f"[{env_name}] Creating environment {env_name}; Command: {cmd}")
        exec_wrapper(cmd.split(" "))
        # install dependencies
        path_to_reqs = get_requirements(instance, temp_dir)
        # Make sure to deactivate so that we can remove the environment.
        # This is necessary if we are running the setup script multiple times.
        cmd = f"source {activate_path} {env_name} && echo 'activate successful' && python -m pip install -r {path_to_reqs} ; source {deactivate_path}"
        logger.info(
            f"[{env_name}] Installing dependencies for {env_name}; Command: {cmd}"
        )
        exec_wrapper(cmd, shell=True)
        os.remove(path_to_reqs)

    elif pkgs == "environment.yml":
        # create environment from yml
        path_to_reqs = get_environment_yml(instance, env_name, temp_dir)
        if "no_use_env" in install and install["no_use_env"]:
            # `conda create` based installation
            cmd = f"{conda_bin_path} create -c conda-forge -n {env_name} python={python_version} -y"
            logger.info(f"[{env_name}] Creating environment {env_name}; Command: {cmd}")
            exec_wrapper(cmd.split(" "))
            # Install dependencies
            cmd = f"{conda_bin_path} env update -f {path_to_reqs}"
            logger.info(
                f"[{env_name}] Installing dependencies for {env_name}; Command: {cmd}"
            )
            exec_wrapper(cmd.split(" "))
        else:
            # `conda env create` based installation
            cmd = f"{conda_bin_path} env create --file {path_to_reqs}"
            logger.info(f"[{env_name}] Creating environment {env_name}; Command: {cmd}")
            exec_wrapper(cmd.split(" "))
        # Remove environment.yml
        os.remove(path_to_reqs)

    else:
        # pkg is a list of packages
        # Create environment + install dependencies
        cmd = f"{conda_bin_path} create -n {env_name} python={python_version} {pkgs} -y"
        logger.info(f"[{env_name}] Creating environment {env_name}; Command: {cmd}")
        exec_wrapper(cmd.split(" "))

    # Install additional packages if specified
    if "pip_packages" in install:
        pip_packages = install["pip_packages"]
        # Make sure to deactivate so that we can remove the environment.
        # This is necessary if we are running the setup script multiple times.
        cmd = f"source {activate_path} {env_name} && python -m pip install {pip_packages} ; source {deactivate_path}"
        logger.info(
            f"[{env_name}] Installing pip packages for {env_name}; Command: {cmd}"
        )
        exec_wrapper(cmd, shell=True)


def collect_install_instructions(repo_full: str, version: str) -> Tuple[List[str], str]:
    """
    Collect install instructions for a repo+version combination.

    Returns:
        A tuple of (pre_install, install) commands.
        If a command is not available, it will be an empty list/string.
    """
    specification = MAP_VERSION_TO_INSTALL[repo_full][version]
    pre_install_cmds = []
    install_cmd = ""
    if "pre_install" in specification:
        # pre_install is a list of commands
        pre_install_cmds = specification["pre_install"]
    if "install" in specification:
        # install is just one command
        install_cmd = specification["install"]
    return pre_install_cmds, install_cmd


def collect_test_exec_cmd(repo_full: str, task_instance: Dict) -> str:
    """
    For a task instance, collect a list of instructions for running tests.
    """
    test_type = MAP_REPO_TO_TEST_FRAMEWORK[repo_full]
    test_directives = get_test_directives(task_instance)
    test_cmd = f"{test_type} {' '.join(test_directives)}"
    return test_cmd


def setup_one_repo_version(
    repo_full: str, repo_path: str, version: str, env_name: str, task: Dict
):
    """
    Main entry for setting up one repo+version combination.
    Put all logic in one function so it's easy to parallelize.
    Args:
        repo_full: full name of the repo, in the form "user/repo".
        repo_path: the cloned repo path on disk.
        version: version of the repo.
        env_name: name of the conda environment to create.
        task: Dict containing task instance.
    """
    logger.info(
        f"[{env_name}] ======= Start setting up for {repo_full} {version} ======="
    )
    clone_repo(repo_full, repo_path)
    logger.info(f"[{env_name}] Cloned {repo_full} to {repo_path}")
    create_conda_env(repo_full, version, repo_path, env_name, task)
    logger.info(
        f"[{env_name}] Created conda environment {env_name} for {repo_full} {version}"
    )
    # "install" and "pre_install" steps are per task;
    # we don't do them here, but instead collects the commands and write them out;
    # this has already been done at a previous step


def get_pr_link_for_task(task: Dict):
    task_id = task["instance_id"]
    repo_long, _, pr_id = task_id.rpartition("-")  # split on the last "-"
    owner, repo_name = repo_long.split("__")
    pr_link = f"https://github.com/{owner}/{repo_name}/pull/{pr_id}"
    return pr_link


def load_task_instances(swe_bench_tasks: str):
    # for parquet version
    df = pd.read_parquet(swe_bench_tasks, engine="pyarrow")
    tasks = json.loads(df.to_json(orient="records"))
    # now form a link to PR for each meta data entry
    for t in tasks:
        pr_link = get_pr_link_for_task(t)
        t["pr_link"] = pr_link
    # fields that are supposed to be list, are encoded as string in parquet
    # fix them here
    for t in tasks:
        fail_to_pass = t["FAIL_TO_PASS"]
        t["FAIL_TO_PASS"] = json.loads(fail_to_pass)
        pass_to_pass = t["PASS_TO_PASS"]
        t["PASS_TO_PASS"] = json.loads(pass_to_pass)
    return tasks
    # this is for the json version, which is deprecated
    # if not os.path.exists(swe_bench_tasks):
    #     raise ValueError("--swe_bench_tasks does not exist")
    # tasks = json.load(open(os.path.abspath(swe_bench_tasks)))
    # if not isinstance(tasks, list):
    #     raise ValueError(f"{swe_bench_tasks} must contain an array of tasks")
    # return tasks


def save_setup_json_files(result_dir: str, setup_map: Dict, tasks_map: Dict):
    """
    Dump maps containing setup information to disk, so other clients can
    use them to find locations of the setup.
    """
    setup_map_path = pjoin(result_dir, "setup_map.json")
    tasks_map_path = pjoin(result_dir, "tasks_map.json")
    with open(setup_map_path, "w") as f:
        json.dump(setup_map, f)
    with open(tasks_map_path, "w") as f:
        json.dump(tasks_map, f)

    print("Done with setup.")
    print(f"setup_map is saved to {setup_map_path}")
    print(f"tasks_map is saved to {tasks_map_path}")


def main(
    swe_bench_tasks: str,
    log_dir: str,
    testbed: str,
    result_dir: str,
    num_processes: int = 1,
    subset_file: Optional[str] = None,
    only_dump_files: bool = False,
):
    """
    Runs set up for each repo/version combination.

    Args:
        swe_bench_tasks (str): Path to the SWE-bench tasks file.
        log_dir (str): Path to the directory where logs will be saved.
        testbed (str): Path to the directory where testbeds will be saved.
        result_dir (str): Path to the directory where results are stored.
        num_processes (int, optional): Number of processes to use.
        subset_file (str, optional): Path to a file indicating which subset to set up.
        only_dump_files (bool, optional): Only dump json files without performing the actual setup.
    """
    # since we are going to store testbed dirs for others to use, we should use absolute path
    testbed = os.path.abspath(testbed)
    # if we just want to dump files, do not touch log and testbed dirs
    if not only_dump_files:
        create_fresh_dir(log_dir)
        create_fresh_dir(testbed)
    create_fresh_dir(result_dir)
    tasks = load_task_instances(swe_bench_tasks)
    # map instance_id to the actual task instance Dict
    tasks_map = {t[KEY_INSTANCE_ID]: t for t in tasks}
    # map instance_id to setup information
    setup_map = {i: {} for i in tasks_map}

    # sometimes we just want to setup a subset of instances for quick experiments
    selected_instances = []  # only used if there is a subset_file
    if subset_file is not None:
        with open(subset_file, "r") as f:
            selected_instances = [line.strip() for line in f.readlines()]

    # keep all information for setting up each entry
    setup_entries = []
    # iterates all tasks, decide which ones need setup,
    # decide the path for their testbed folder, and save this path to task_map
    for instance_id, task in tasks_map.items():
        if subset_file is not None and instance_id not in selected_instances:
            continue
        repo_full = task["repo"]  # "astropy/astropy"
        repo_short = instance_id.rsplit("-", 1)[0]  # "astropy"
        version = task["version"]  # "4.2"
        # name for both conda env and testbed folder
        env_name = f"setup_{repo_short}__{version}"
        repo_path = pjoin(testbed, repo_short, env_name)
        pre_install_cmds, install_cmd = collect_install_instructions(repo_full, version)
        test_cmd = collect_test_exec_cmd(repo_full, task)
        # keys in setup_map
        setup_map[instance_id]["repo_path"] = repo_path
        setup_map[instance_id]["env_name"] = env_name
        setup_map[instance_id]["pre_install"] = pre_install_cmds
        setup_map[instance_id]["install"] = install_cmd
        setup_map[instance_id]["test_cmd"] = test_cmd
        collected_entry_env_names = [e[3] for e in setup_entries]
        if env_name in collected_entry_env_names:
            # this repo+version combination has been recorded before
            continue
        # should really do setup
        setup_entries.append((repo_full, repo_path, version, env_name, task))

    # check whether we are required to perform the actual setup
    if only_dump_files:
        save_setup_json_files(result_dir, setup_map, tasks_map)
        return

    setup_entries = sorted(setup_entries, key=lambda x: x[3])
    all_env_names = [e[3] for e in setup_entries]
    logger.info(f"env_name for all setup entries: {all_env_names}")

    # Now we have all the information for setting up each entry
    num_setup_entries = len(setup_entries)
    num_processes = min(num_processes, num_setup_entries)
    if num_setup_entries == 0:
        logger.info("No setup needed.")
        return

    logger.info("Starting parallel setup.")
    logger.info(f"\tNumber of setup tasks: {num_setup_entries}")
    logger.info(f"\tNumber of processes: {num_processes}")
    try:
        if num_processes == 1:
            for entry in setup_entries:
                setup_one_repo_version(*entry)
        else:
            # parallel
            pool = Pool(processes=num_processes)
            pool.starmap(setup_one_repo_version, setup_entries)
            pool.close()
            pool.join()
    finally:
        # Done with the actual work.
        save_setup_json_files(result_dir, setup_map, tasks_map)


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.realpath(__file__))
    root_dir = os.path.dirname(script_dir)
    # we always read from this file, so put this as a default instead of required
    default_tasks_file = pjoin(
        root_dir, "data", "test-00000-of-00001-dc7762b94638c186.parquet"
    )

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log_dir", type=str, help="Path to log directory", required=True
    )
    parser.add_argument(
        "--swe_bench_tasks",
        type=str,
        help="Path to SWE-bench task instances file",
        default=default_tasks_file,
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
        default=1,
    )
    parser.add_argument(
        "--subset_file",
        type=str,
        help="(Optional) Path to a file containing a subset of instances to setup. Each line should contain one instace id to be set up.",
        default=None,
    )
    parser.add_argument(
        "--only_dump_files",
        default=False,
        action="store_true",
        help="Only dump json files without performing the actual setup.",
    )
    args = parser.parse_args()
    main(**vars(args))
