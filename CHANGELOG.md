# Changelog

All notable changes to the PyPI package for SWE-bench ([`swebench`](https://pypi.org/project/swebench/)) will be documented in this file.

Prior to version 1.0.0, not all deployed versions are listed, as the PyPI package was going through development and testing. The noteworthy versions and the respective changes that were introduced by that version are included. All versions 1.0.0 onwards are fully listed.

## [1.0.4] - 4/5/2024
* Fixed `env_list` parsing. 5be59d665233ffb63b9beb30b2740cc41098e51f
* Updated `ExecWrapper`, `LogWrapper` logic for harness. 231a2b205c5ca9ddcb126b73b22667d79e1b6108

## [1.0.2] - 4/2/2024
* Added `try/catch` around `lsof` based clean up for `run_evaluation.py`. 3fb2179a5c69737465f916898e8708adffff9914
* Fixed `get_eval_refs` function. 12a287a9591cb4a0d65483f0c8bfaa3375285bfc
* Fixed `seaborn` log parser. 0372b6a9ff62516067fb26f602163c231d818163

## [1.0.1] - 3/31/2024
First working version. We strongly recommend not using versions older than this one.
* Added logging for failed installations. 58d24d1b65b95ed96d57805604aca7adca49861d
* Added missing `datasets` dependency. 68e89ef8d099ca5c23a8fd5681e3f990cf729fd6
* Reorganized repository to be directly build-able as a PyPI package. 548bdbffb2ac5f0a09c1d7eb95bbee1bce126233

## [0.6.9 - 0.6.9.2] - 3/31/2024 
> ⚠️ Do NOT use these versions. The PyPI package for these versions was under development. Specifically, some of the evaluation configurations required re-validation. A detailed report for the failures and our recovery from it are detailed in [Bug Report 4/5/2024](docs/reports/bug_report_20240405.md).

## [0.6.1] - 3/14/2023
* Added minor conditions to make `run_evaluation` more robust (e.g. exit on empty predictions)
* Added logic that conditions conda link download based on which architecture/platform (e.g. x86, arm) the code is being run on.
* Added classes to unify `subprocess` execution arguments + make them more consistent throughout the codebase. Also remove `shell=True` flag when not necessary.
* Added deterministic hashing of model name when creating certain testbed paths, defends against https://github.com/conda/conda/issues/12250
* Fixed key errors across the `metrics/` folder.
* Reorganized `harness` code. Moved constants into a separate file to improve readability.

## [0.4.8] - 11/8/2023
* `run_evaluation` can be imported to make running the evaluation harness of SWE-bench more accessible.
* Add condition in `harness/context_manager.py` to skip installation if no instructions are provided.
* Add functionality to check and remove logs with `AttributeError` or `ImportError`
* Add support for HumanEval dataset.
* Add support for relative paths for `log_dir` and `testbed` arguments of evaluation.
* Minor renaming for `metrics/report.py` variables.

## [0.4.3] - 11/5/2023
Introducing the initial release of SWE-Bench, a novel benchmark that introduces "software engineering as a task". Given a codebase and an issue, a model is tasked with writing a `.patch` file that addresses the desired changes.

Please view the `README.md` for information on how to run the repository, and check out our paper, [SWE-bench: Can Language Models Resolve Real-World GitHub Issues?](https://arxiv.org/abs/2310.06770), for full details on the project.

We will maintain a leaderboard on the SWE-bench public [website](http://swe-bench.github.io). We will release details soon on how to submit your generations for evaluation to be included on the leaderboard.

## [< 0.4.3] - 11/4/2023
> ⚠️ Do NOT use these versions. The PyPI package was under development for these versions and will not work properly.