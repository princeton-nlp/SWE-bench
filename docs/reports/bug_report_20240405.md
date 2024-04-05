# Evaluation Harness Repair Report
April 5, 2024

In this report, we detail our resolution of harness failures that we and SWE-bench practitioners observed in January 2024.
The root cause of this issue is due to SWE-bench's reliance on the `latest` conda version for environment creation.
We include details about the failure modes and resolution found in our investigations.
As of this report's release, SWE-bench evaluation has been restored to work properly (`swebench>=1.0.1`).

## Failure Modes
From versions `0.6.9` to `1.0.0`, we were recovering from multiple failures arising when running SWE-bench task instances.
Specifically, we investigated causes for conda based installation failing for the validation and execution harnesses.
The root causes of the issues are four-fold:

**1. `latest` Conda Link**: The `latest` conda link, which the harness originally used, is updated overtime to point at different versions. For example, based on the [Miniconda archive](https://repo.anaconda.com/miniconda/), the URL for the latest download (`https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh`) pointed at different links overtime. Also see https://github.com/conda/conda/issues/13701. Due to this change, the conda environment we define for each repo/version may fail to be created at a later date.
- Severity: 🔴 High (100+ Task Instances Affected)
- Affected Repositories: astropy, matplotlib, sympy, sphinx, scikit-learn, requests, xarray

<details>
<summary>Click for Example</summary>
This is an example of the log to console that showed up when the conda environment for sphinx 4.1 failed to build properly.

```bash
❌ Evaluation failed: Command '. /home/ubuntu/SWE-agent/evaluation/testbed/predictions/sphinx-doc__sphinx/4.1/tmpe4u_b189/miniconda3/bin/activate sphinx-doc__sphinx__4.1 && 
conda install gxx_linux-64 gcc_linux-64 make -y' returned non-zero exit status 2.
multiprocessing.pool.RemoteTraceback: 
"""
Traceback (most recent call last):
File "/home/ubuntu/miniconda3/envs/swe-agent/lib/python3.9/multiprocessing/pool.py", line 125, in worker
    result = (True, func(*args, **kwds))
File "/home/ubuntu/miniconda3/envs/swe-agent/lib/python3.9/multiprocessing/pool.py", line 48, in mapstar
    return list(map(*args))
File "/home/ubuntu/miniconda3/envs/swe-agent/lib/python3.9/site-packages/swebench/harness/engine_evaluation.py", line 167, in main
    setup_testbed(data_groups[0])
File "/home/ubuntu/miniconda3/envs/swe-agent/lib/python3.9/site-packages/swebench/harness/engine_validation.py", line 90, in setup_testbed
    with TestbedContextManager(
File "/home/ubuntu/miniconda3/envs/swe-agent/lib/python3.9/site-packages/swebench/harness/context_manager.py", line 364, in __enter__
    self.exec(cmd, shell=True)
File "/home/ubuntu/miniconda3/envs/swe-agent/lib/python3.9/site-packages/swebench/harness/context_manager.py", line 59, in __call__
    raise e
File "/home/ubuntu/miniconda3/envs/swe-agent/lib/python3.9/site-packages/swebench/harness/context_manager.py", line 51, in __call__
    output = subprocess.run(cmd, **combined_args)
File "/home/ubuntu/miniconda3/envs/swe-agent/lib/python3.9/subprocess.py", line 528, in run
    raise CalledProcessError(retcode, process.args,
subprocess.CalledProcessError: Command '. /home/ubuntu/SWE-agent/evaluation/testbed/predictions/sphinx-doc__sphinx/4.1/tmpe4u_b189/miniconda3/bin/activate 
sphinx-doc__sphinx__4.1 && conda install gxx_linux-64 gcc_linux-64 make -y' returned non-zero exit status 2.
"""
```
</details>


**2. Machine Discrepancies**: Different machines (e.g. x86, arm) require different miniconda installers. Consequently, on rare occasion, an installation script may work for one machine, but not for another.
- 🟡 Low (< 10)
- Affected Repositories: scikit-learn
<details>
<summary>Click for Example</summary>
To accommodate for the difference in installation between x86 and arch64 for scikit-learn, we added the `arch_specific_packages` field that allows us to specify what additional packages to install.

```python
"arch_specific_packages": {
    "aarch64": "gxx_linux-aarch64 gcc_linux-aarch64 make",
}
```

A clause in the `harness/context_manager.py` file then takes care of adding this installation to the conda commands.
</details>

**3. Which Conda?**: Even if the conda environment is created successfully, different conda versions will build the environment differently. For instance, we found that given the same installation instructions (e.g. `pip install numpy flask seaborn`), two different miniconda versions (e.g. `py38_23.11.0-1` and `py311_23.11.0-1`) will create environments that differ in the versions of installed pypi packages. As a result, newer conda versions might build environments differently than prior versions. The main implication of this is that PyPI packages are installed at different versions, which could then affect whether the repository is installed successfully + the behavior of the repository.
- 🟠 Medium (10+)
- Affected Repositories: django, sympy

**4. PyPI Package Updates**: Assuming failure modes #1 and #2 don't occur (conda environment is created + is set up correctly), a last source of potential error is that the PyPI package is updated by the maintainers. At this time, based on the extent of our investigation, this is not a source of error for any task instances. However, if future versions of a PyPI package break prior functionality, this may cause an error.
- 🟠 Medium (10+)
- Affected Repositories: flask, sphinx
<details>
<summary>Click for Example</summary>
We write installation outputs per task instance to a log file. A log file will usually have the following kind of standard output written to it that describes which versions of libraries have been installed and included in the environment.

```bash
Requirement already satisfied: numpy!=1.24.0,>=1.17 in /n/fs/p-swe-bench/temp/seaborn/tmphkkamwwi/miniconda3/envs/mwaskom__seaborn__0.12/lib/python3.9/site-packages (from seaborn==0.12.2.dev0) (1.25.2)
Requirement already satisfied: pandas>=0.25 in /n/fs/p-swe-bench/temp/seaborn/tmphkkamwwi/miniconda3/envs/mwaskom__seaborn__0.12/lib/python3.9/site-packages (from seaborn==0.12.2.dev0) (2.1.0)
Requirement already satisfied: matplotlib!=3.6.1,>=3.1 in /n/fs/p-swe-bench/temp/seaborn/tmphkkamwwi/miniconda3/envs/mwaskom__seaborn__0.12/lib/python3.9/site-packages (from seaborn==0.12.2.dev0) (3.7.2)
Requirement already satisfied: pytest in /n/fs/p-swe-bench/temp/seaborn/tmphkkamwwi/miniconda3/envs/mwaskom__seaborn__0.12/lib/python3.9/site-packages (from seaborn==0.12.2.dev0) (7.4.1)
```

Over time, the version number may increase. The solution for this is to add caps for the versions of pypi packages (e.g. `Jinja2<3.0`)
</details>

## Investigation
To identify and then fix these issues, we carried out the following steps:
* Updated the logging mechanism for the harness to record not just task instance logs, but also testbed logging. This way, a history of how a conda environment is created + whether it installed is recorded, enabling easier debugging in the future.
* Re-ran task instance validation with a sweep across all Miniconda links between March 2023 and February 2024. We do this to "search" for which conda installation(s) correctly recreate the execution environments.
* Based on testbed logs, we manually + automatically identify cases fitting failure modes 1-4 and address them in a variety of ways:
    * Fixing the conda version to `py39_23.10.0-1`, which minor exceptions for two repo/version installation specifications.
    * Adding `arch_specific_packages` to specify additional packages that must be installed for arch machines.
    * Made modifications as needed to pypi package versioning in the installation specifications.
* Based on task instance level logs, we identified discrepancies in logs stemming from later PyPI package updates, then modified the `pip` installation logic + configurations to cap the versions of specific libraries (e.g. `Jinja2<3.0`).
* The majority of our recovery efforts took place on an x86 machine. We also made efforts to reflect these changes on arm machines. We have support for other architectures, but have *not* verified them.

## Outcomes
We introduce the following fixes that are solutions to the discussed problems, which is generally captured by #65:
* Fix conda version to `py39_23.10.0-1`
* Specify specific pip package versions to install.
* Add missing pip packages that need to be installed due to differences over time.
* Add logic that cleans up + enforces versioning for `requirements.txt` and `environment.yml` based installation.
* Remove `shell=True` from the majority of `subprocess.run` calls to avoid local machine settings potentially interfering with the call.
* We re-run validation to re-verify the F2P and P2P tests for every task instance.
* We release the `check_harness.jsonl` file, which is a file of 128 gold predictions (one per unique repo/version) you can run to verify that your harness is working.

Our diagnosis is that:
* Failure mode #1 should be *completely resolved*. We no longer rely on `latest`, in favor of set, prior versions of miniconda.
* Failure mode #2 should be *completely resolved* for x86 and arch machines.
* Failure mode #3 should be *completely resolved*. Same reason as #1 + we ran a sweep across all miniconda versions to identify the one that reproduces all task instances correctly, which was `py39_23.10.0-1`.
* Failure mode #4 should be *completely resolved for now*. However, as time goes on, it is possible that later versions of dependencies cause issues. The permanent solution to this problem is to specify a cap version for all pypi packages included in the installation procedure. (If you have the time, we would greatly appreciate contributions that resolve this case! Feel free to raise an issue if you're interested and have questions, or a pull request if you have a fix towards this end 😁)

## Deliverables
* Please use `swebench>=1.0.1`.
* If you'd like to check that your machine is compatible with the harness, run evaluataion with `check_harness.jsonl` as the predictions. **[Coming soon]**
* Use the updated `swe-bench.json` file to evaluate on the test set. **[Coming soon]**

✍️ Carlos & John