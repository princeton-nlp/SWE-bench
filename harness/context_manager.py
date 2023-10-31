import logging, os, subprocess

from constants import (
    APPLY_PATCH_FAIL,
    APPLY_PATCH_PASS,
    INSTALL_FAIL,
    INSTALL_PASS,
    INSTALL_TIMEOUT,
    KEY_INSTANCE_ID,
    KEY_MODEL,
    MAP_REPO_TO_INSTALL,
    MAP_REPO_TO_TEST_FRAMEWORK,
    MAP_VERSION_TO_INSTALL,
    RESET_FAILED,
    TESTS_FAILED,
    TESTS_PASSED,
    TESTS_TIMEOUT,
    TESTS_ERROR,
)
from tempfile import TemporaryDirectory
from typing import Dict, List
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
logger_testbed = logging.getLogger("testbed_context_manager")


class TestbedContextManager:
    def __init__(
        self,
        task_instances: List,
        log_dir: str,
        path_conda: str = None,
        testbed: str = None,
        verbose: bool = False,
        timeout: int = None,
        temp_dir: str = None,
    ):
        """
        Initialize testbed context. Creates temporary directories and groups task instances
        by repo/version.

        Args:
            task_instances (list): List of task instances
            log_dir (str): Path to log directory
            path_conda (str): Path to conda installation
            testbed (str): Path to testbed directory
            verbose (bool): Whether to show logs
            timeout (int): Timeout for actions
            temp_dir (str): Path to temporary directory
        """
        logger_testbed.propagate = verbose
        self.verbose = verbose
        self.old_dir = os.getcwd()
        self.log_dir = log_dir
        self.timeout = timeout
        self.subprocess_args = {"check": True, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}

        # Create log, temp directories if they don't exist
        if not os.path.exists(self.log_dir):
            logger_testbed.info(f"[Testbed] Creating log directory {self.log_dir}")
            os.makedirs(self.log_dir, exist_ok=True)
        if temp_dir is not None and not os.path.exists(temp_dir):
            logger_testbed.info(f"[Testbed] Creating temp directory {temp_dir}")
            os.makedirs(temp_dir, exist_ok=True)

        # Set up conda path, create in temp directory if None
        if path_conda is not None:
            self.temp_dir_conda = None
            self.path_conda = path_conda
        else:
            self.temp_dir_conda = TemporaryDirectory(dir=temp_dir)
            self.path_conda = self.temp_dir_conda.name
        logger_testbed.info(f"[Testbed] Using conda path {self.path_conda}")

        # Set up testbed path, create in temp directory if None
        if testbed is not None:
            self.temp_dir_work = None
            self.testbed = testbed
        else:
            self.temp_dir_work = TemporaryDirectory(dir=temp_dir)
            self.testbed = self.temp_dir_work.name
        logger_testbed.info(f"[Testbed] Using working directory {self.testbed} for testbed")

        # Sort task instances by created_at
        self.task_instances = sorted(task_instances, key=lambda x: x["created_at"], reverse=True)

        # Group repos by repo, then version
        self.task_instances_grouped = {}
        for instance in self.task_instances:
            # Create test command from framework + directives
            test_type = MAP_REPO_TO_TEST_FRAMEWORK[instance["repo"]]
            test_directives = get_test_directives(instance)
            instance["test_cmd"] = f"{test_type} {' '.join(test_directives)}"

            # Group task instances by repo, version
            repo = instance["repo"]
            version = instance["version"] if "version" in instance else None
            if repo not in self.task_instances_grouped:
                self.task_instances_grouped[repo] = {}
            if version not in self.task_instances_grouped[repo]:
                self.task_instances_grouped[repo][version] = []
            self.task_instances_grouped[repo][version].append(instance)

        # Log grouped task instances to be run
        self.setup_refs = {}
        for repo, map_version_to_instances in self.task_instances_grouped.items():
            logger_testbed.info(f"[Testbed] Repo {repo}: {len(map_version_to_instances)} versions")

            # Determine instances to use for environment installation
            self.setup_refs[repo] = {}
            for version, instances in map_version_to_instances.items():
                logger_testbed.info(f"[Testbed] \tVersion {version}: {len(instances)} instances")
                self.setup_refs[repo][version] = instances[0]

        # Remove None versions, versions not in MAP_VERSION_TO_INSTALL
        self._custom_restraints()

    def __enter__(self):
        """
        Set up testbed (conda environments, git repositories)
        """
        # If path_conda not provided, create temporary miniconda3 installation
        if self.temp_dir_conda is not None:
            # Set up the paths for Miniconda
            self.path_conda = os.path.join(self.path_conda, "miniconda3")
            os.mkdir(self.path_conda)
            miniconda_sh = os.path.join(self.path_conda, "miniconda.sh")
            logger_testbed.info(f"No conda path provided, creating temporary install in {self.path_conda}...")

            # Download Miniconda installer
            download_cmd = [
                "wget",
                "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh",
                "-O",
                miniconda_sh,
            ]
            subprocess.run(download_cmd, **self.subprocess_args)

            # Install Miniconda
            install_cmd = ["bash", miniconda_sh, "-b", "-u", "-p", self.path_conda]
            subprocess.run(install_cmd, **self.subprocess_args)

            # Clean up the installer
            os.remove(miniconda_sh)
        logger_testbed.info(f"[Testbed] Using conda path {self.path_conda}")

        # Set up conda executables, get existing environments
        self.path_conda = os.path.abspath(self.path_conda)
        path_activate = os.path.join(self.path_conda, "bin", "activate")
        exec_type = "mamba" if "mamba" in self.path_conda else "conda"
        exec_cmd = os.path.join(self.path_conda, "bin", exec_type)
        env_list = get_conda_env_names(exec_cmd)

        # Set up testbed (environment, github repo) for each repo
        for repo, version_to_setup_ref in self.setup_refs.items():
            repo_prefix = repo.replace("/", "__")

            # Run any repo-level installation commands if provided
            if repo in MAP_REPO_TO_INSTALL:
                install_cmd = MAP_REPO_TO_INSTALL[repo]
                logger_testbed.info(f"[Testbed] Running custom install command for {repo}: {install_cmd}")
                subprocess.run(install_cmd, shell=True, **self.subprocess_args)

            # Create conda environment per version of the repo
            for version, install in MAP_VERSION_TO_INSTALL[repo].items():
                # Skip if none of the task instances are for this version
                if version not in version_to_setup_ref:
                    continue

                # Name for both environment and github repo
                env_name = f"{repo_prefix}__{version}"
                logger_testbed.info(f"[Testbed] Setting up testbed for {env_name}")

                # Clone github per repo/version
                repo_path = os.path.join(self.testbed, env_name)
                if not os.path.exists(repo_path):
                    clone_repo(repo, repo_path)
                    logger_testbed.info(f"[Testbed] Cloned {repo} to {repo_path}")
                else:
                    logger_testbed.info(
                        f"[Testbed] Repo for {repo_prefix} version {version} exists: {repo_path}; skipping"
                    )

                # Skip if conda environment already exists
                if env_name in env_list:
                    logger_testbed.info(
                        f"[Testbed] Environment {env_name} already exists; skipping"
                    )
                    continue

                # Get setup reference instance
                setup_ref_instance = version_to_setup_ref[version]

                # Create conda environment according to install instructinos
                pkgs = install["packages"] if "packages" in install else ""
                if pkgs == "requirements.txt":
                    # Create environment
                    cmd = f"{exec_cmd} create -n {env_name} python={install['python']} -y"
                    logger_testbed.info(f"[Testbed] Creating environment {env_name}; Command: {cmd}")
                    subprocess.run(cmd, shell=True, **self.subprocess_args)

                    # Install dependencies
                    path_to_reqs = get_requirements(setup_ref_instance, self.testbed)
                    cmd = f"source {path_activate} {env_name} && pip install -r {path_to_reqs}"
                    logger_testbed.info(f"[Testbed] Installing dependencies for {env_name}; Command: {cmd}")
                    subprocess.run(cmd, shell=True, **self.subprocess_args)
                    os.remove(path_to_reqs)
                elif pkgs == "environment.yml":
                    # Create environment from yml
                    path_to_reqs = get_environment_yml(setup_ref_instance, env_name, self.testbed)
                    if "no_use_env" in install and install["no_use_env"]:
                        # `conda create` based installation
                        cmd = f"{exec_cmd} create -c conda-forge -n {env_name} python={install['python']} -y"
                        logger_testbed.info(f"[Testbed] Creating environment {env_name}; Command: {cmd}")
                        subprocess.run(cmd, shell=True, **self.subprocess_args)

                        # Install dependencies
                        cmd = f"{exec_cmd} env update -f {path_to_reqs}"
                        logger_testbed.info(f"[Testbed] Installing dependencies for {env_name}; Command: {cmd}")
                        subprocess.run(cmd, shell=True, **self.subprocess_args)
                    else:
                        # `conda env create` based installation
                        cmd = f"{exec_cmd} env create --file {path_to_reqs}"
                        logger_testbed.info(f"[Testbed] Creating environment {env_name}; Command: {cmd}")
                        subprocess.run(cmd, shell=True, **self.subprocess_args)

                    # Remove environment.yml
                    os.remove(path_to_reqs)
                else:
                    # Create environment + install dependencies
                    cmd = f"{exec_cmd} create -n {env_name} python={install['python']} {pkgs} -y"
                    logger_testbed.info(f"[Testbed] Creating environment {env_name}; Command: {cmd}")
                    subprocess.run(cmd, shell=True, **self.subprocess_args)

                # Install additional packages if specified
                if "pip_packages" in install:
                    cmd = f"source {path_activate} {env_name} && pip install {install['pip_packages']}"
                    logger_testbed.info(f"[Testbed] Installing pip packages for {env_name}; Command: {cmd}")
                    subprocess.run(cmd, shell=True, **self.subprocess_args)

        return self

    def get_distributed_tasks(self) -> List:
        """
        Create task group (instances + keywords) for each repo/version

        Returns:
            list: List of task groups, each group containing task instances
                from the same repo with the same version
        """
        distributed_tasks = []
        for repo, map_version_to_instances in self.task_instances_grouped.items():
            repo_prefix = repo.replace("/", "__")
            for version, instances in map_version_to_instances.items():
                env_name = f"{repo_prefix}__{version}"
                task_set = {
                    "conda_path": self.path_conda,
                    "log_dir": self.log_dir,
                    "task_instances": instances,
                    "testbed": os.path.join(self.testbed, env_name),
                    "timeout": self.timeout,
                    "venv": env_name,
                    "version": version,
                    "verbose": self.verbose,
                }
                distributed_tasks.append(task_set)
        return distributed_tasks

    def _custom_restraints(self):
        """
        Custom restraints per repo
        """
        for repo, group in self.task_instances_grouped.items():
            if None in group:
                logger_testbed.info(f"[Testbed] Removed None version from repo {repo}")
                del group[None]
            versions = list(group.keys())
            for version in versions:
                if version not in MAP_VERSION_TO_INSTALL[repo]:
                    logger_testbed.info(f"[Testbed] Removed {version} version from repo {repo} (Install instructions not given)")
                    del group[version]

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.temp_dir_work is not None:
            self.temp_dir_work.cleanup()
        if self.temp_dir_conda is not None:
            self.temp_dir_conda.cleanup()


logger_taskenv = logging.getLogger("taskenv_context_manager")


class TaskEnvContextManager:
    def __init__(
        self,
        instance: Dict,
        testbed: str,
        venv: str,
        log_dir: str,
        conda_path: str,
        verbose: bool = False,
        timeout: int = None,
        is_eval: bool = False,
    ):
        """
        Sets up execution context for a single task instance

        Args:
            instance (dict): Task instance
            testbed (str): Path to testbed directory
            venv (str): Name of conda environment (should exist in conda_path)
            log_dir (str): Path to log directory
            conda_path (str): Path to conda installation
            verbose (bool): Whether to show logs
            timeout (int): Timeout for actions
            is_eval (bool): Whether this is for evaluating a model on SWE Bench
                (Mainly for logging purposes)
        """
        logger_taskenv.propagate = verbose
        self.instance = instance
        self.testbed = testbed
        self.testbed_name = testbed.split("/")[-1]
        self.venv = venv
        self.conda_path = conda_path
        self.log_file = os.path.join(log_dir, f"{instance[KEY_INSTANCE_ID]}.log")
        self.is_eval = is_eval
        if is_eval:
            self.log_file = os.path.join(log_dir, f"{instance[KEY_INSTANCE_ID]}.{instance[KEY_MODEL]}.eval.log")
        self.cmd_activate = (f"source {os.path.join(self.conda_path, 'bin', 'activate')} {self.venv}")
        self.timeout = timeout
        self.cwd = os.getcwd()

    def __enter__(self):
        """
        Enter task environment, set up log file
        """
        os.chdir(self.testbed)
        with open(self.log_file, "w") as f:
            f.write(f"Task Metadata:\n\t- Instance ID: {self.instance[KEY_INSTANCE_ID]}\n\t- Testbed: {self.testbed}\n\t- Virtual Env.: {self.venv}\n")
            if self.is_eval:
                f.write(f"\t- Evaluation Model: {self.instance[KEY_MODEL]}\n")
        return self

    def reset_task_env(self, instance: Dict):
        """
        Reset task environment + testbed and checkout base commit of given task instance

        Args:
            instance (dict): Task instance
        Returns:
            bool: True if reset successful, False otherwise
        """
        subprocess_args = {"check": True, "shell": True, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        try:
            # Remove all paths in .gitignore
            if os.path.exists(".gitignore"):
                with open(".gitignore", "r") as f:
                    for line in f.readlines():
                        if line.startswith("#") or line.strip() == "":
                            continue
                        subprocess.run(f"rm -rf {line}", **subprocess_args)

            # Reset git repo + checkout base commit
            subprocess.run("git restore .", **subprocess_args)
            subprocess.run("git reset HEAD .", **subprocess_args)
            subprocess.run("git clean -fdx", **subprocess_args)
            subprocess.run(f"git -c advice.detachedHead=false checkout {instance['base_commit']}", **subprocess_args)
            logger_taskenv.info(f"[{self.testbed_name}] [{instance[KEY_INSTANCE_ID]}] Reset task environment to {instance['base_commit']}")
            return True
        except Exception as e:
            err_msg = (f"{RESET_FAILED}; Failed to reset task environment to {instance['base_commit']}: {e}")
            logger_taskenv.error(f"[{self.testbed_name}] {err_msg}")
            with open(self.log_file, "a") as f:
                f.write(err_msg)
            return False

    def run_install_task(self, instance: Dict) -> bool:
        """
        Run installation for task instance

        Args:
            instance (dict): Task instance
        Returns:
            bool: True if installation successful, False otherwise
        """
        # Get installation instructions by repo/version
        specifications = MAP_VERSION_TO_INSTALL[instance["repo"]][instance["version"]]

        # Run pre-install set up if provided
        if "pre_install" in specifications:
            for pre_install in specifications["pre_install"]:
                cmd_pre_install = f"{self.cmd_activate}; {pre_install}"
                logger_taskenv.info(f"[{self.testbed_name}] [{instance[KEY_INSTANCE_ID]}] Running pre-install setup command: {cmd_pre_install}")
                out_pre_install = subprocess.run(
                    cmd_pre_install,
                    shell=True,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=self.timeout,
                )
                with open(self.log_file, "a") as f:
                    f.write(f"Pre-installation Command: {cmd_pre_install}\n")
                    f.write(f"Std. Output: {out_pre_install.stdout}\n")
                    f.write(f"Std. Error: {out_pre_install.stderr}\n")
                if out_pre_install.returncode != 0:
                    logger_taskenv.error(f"[{self.testbed_name}] [{instance[KEY_INSTANCE_ID]}] Pre-install setup failed")
                    with open(self.log_file, "a") as f:
                        f.write(f"\n{INSTALL_FAIL}\n")
                    return False

        cmd_install = f"{self.cmd_activate}; {specifications['install']}"
        logger_taskenv.info(f"[{self.testbed_name}] [{instance[KEY_INSTANCE_ID]}] Installing with command: {cmd_install}")
        try:
            # Run installation command
            out_install = subprocess.run(
                cmd_install,
                shell=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout,
            )
            # Write installation logs to log file
            with open(self.log_file, "a") as f:
                f.write(f"Installation Command: {cmd_install}\n")
                f.write(f"Std. Output: {out_install.stdout}\n")
                f.write(f"Std. Error: {out_install.stderr}\n")

            if out_install.returncode != 0:
                # Installation failed
                logger_taskenv.error(f"[{self.testbed_name}] [{instance[KEY_INSTANCE_ID]}] Installation failed")
                with open(self.log_file, "a") as f:
                    f.write(f"\n{INSTALL_FAIL}\n")
                return False

            # Installation successful
            logger_taskenv.info(f"[{self.testbed_name}] [{instance[KEY_INSTANCE_ID]}] Installation successful")
            with open(self.log_file, "a") as f:
                f.write(f"\n{INSTALL_PASS}\n")
            return True
        except subprocess.TimeoutExpired:
            # Installation timed out
            logger_taskenv.error(f"[{self.testbed_name}] [{self.instance[KEY_INSTANCE_ID]}] Installation timed out")
            with open(self.log_file, "a") as f:
                f.write(f"\n{INSTALL_TIMEOUT}\n")
            return False

    def apply_patch(
        self, patch: str, patch_type: str = "", revert: bool = False
    ) -> bool:
        """
        Apply patch to task environment

        Args:
            patch (str): Plaintext of patch to apply
            patch_type (str): Type of patch (e.g. "eval", "test")
        Returns:
            bool: True if patch applied successfully, False otherwise
        """
        # If patch is `None`, indicate in log and skip
        if patch is None:
            logger_taskenv.error(f"[{self.testbed_name}] [{self.instance[KEY_INSTANCE_ID]}] Patch is `None` ({patch_type})")
            with open(self.log_file, "a") as f:
                f.write(f"{APPLY_PATCH_FAIL}; Prediction patch is `None`")
            return False

        # Write patch to temporary patch file in parent directory
        patch_path = os.path.join(
            os.path.dirname(self.testbed.rstrip("/")),
            f"temp_{self.instance[KEY_INSTANCE_ID]}_{patch_type}.patch",
        )
        with open(patch_path, "w") as f:
            f.write(patch)

        # Apply patch to testbed directory
        apply_cmd = f"git apply -v -R {patch_path}" if revert else f"git apply -v {patch_path}"
        out_patch = subprocess.run(
            apply_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        os.remove(patch_path)

        log_cmd = "Revert" if revert else "Apply"
        if out_patch.returncode != 0:
            # Patch apply failed
            logger_taskenv.error(f"[{self.testbed_name}] [{self.instance[KEY_INSTANCE_ID]}] {log_cmd} patch failed ({patch_type})")
            with open(self.log_file, "a") as f:
                f.write(f"{APPLY_PATCH_FAIL}; ({patch_type})\nOutput:\n")
                f.write(out_patch.stdout)
                f.write(out_patch.stderr)
            return False

        # Patch apply succeeded
        logger_taskenv.info(f"[{self.testbed_name}] [{self.instance[KEY_INSTANCE_ID]}] {log_cmd} patch successful ({patch_type})")
        with open(self.log_file, "a") as f:
            f.write(f"{APPLY_PATCH_PASS} ({patch_type})\n")
        return True

    def run_tests_task(self, instance: Dict):
        """
        Run tests for task instance

        Args:
            instance (dict): Task instance
        Returns:
            bool: True if test script ran successfully, False otherwise
        """
        try:
            # Run test command for task instance
            test_cmd = f"{self.cmd_activate}; {instance['test_cmd']}"
            with open(self.log_file, "a") as f:
                f.write(f"Test Script: {test_cmd};\n")
            out_test = subprocess.run(test_cmd, shell=True, capture_output=True, timeout=self.timeout)

            # Write test results to log file
            with open(self.log_file, "a") as f:
                f.write(f"Output:\n")
                f.write(out_test.stdout.decode("utf-8"))
                f.write(out_test.stderr.decode("utf-8"))
                if out_test.returncode != 0:
                    f.write(f"\n{TESTS_FAILED}\n")
                else:
                    f.write(f"\n{TESTS_PASSED}\n")

            logger_taskenv.info(f"[{self.testbed_name}] [{instance[KEY_INSTANCE_ID]}] Test script run successful")
            return True
        except subprocess.TimeoutExpired:
            # Test command run timed out
            logger_taskenv.error(f"[{self.testbed_name}] [{instance[KEY_INSTANCE_ID]}] Test script run time out {self.timeout}")
            with open(self.log_file, "a") as f:
                f.write(f"{TESTS_TIMEOUT} after {self.timeout} seconds\n")
            return False
        except Exception as e:
            # Test command run failed
            logger_taskenv.error(f"[{self.testbed_name}] [{instance[KEY_INSTANCE_ID]}] Test script run failed")
            with open(self.log_file, "a") as f:
                f.write(f"{TESTS_ERROR}: {e}")
            return False

    def __exit__(self, exc_type, exc_value, exc_traceback):
        os.chdir(self.cwd)
