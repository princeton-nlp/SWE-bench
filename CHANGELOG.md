# Changelog

All notable changes to the PyPI package for SWE-bench ([`swebench`](https://pypi.org/project/swebench/)) will be documented in this file.

Prior to version 1.1.0, not all deployed versions are listed, as the PyPI package was going through development and testing. The noteworthy versions and the respective changes that were introduced by that version are included. All versions 1.1.0 onwards are fully listed.

## [Unreleased]

Breaking changes:
* The run report is written to `logs/evaluation/<run_id>/results.json` instead of
  `<model>.<run_id>.json` in the current directory. `--report_dir` / `--report-dir` is
  gone: the report always sits with the run's other artifacts.
* `RUN_VALIDATION_LOG_DIR` is gone. Nothing read it, and the `run_validation.sh` the
  collection docs mention does not exist in this repository.
* Evaluation logs are written to `logs/evaluation/<run_id>` instead of
  `logs/run_evaluation/<run_id>`. Move an existing directory to keep past runs
  readable by `swebench report` and `swebench submit package`:
  `mv logs/run_evaluation logs/evaluation`.

Added:
* `swebench infer` runs mini-SWE-agent over a dataset, writing predictions and
  trajectories to `logs/inference/<run_id>`.
* `swebench submit package|publish|register|verify` build and check a leaderboard
  submission, and `swebench submit hf` publishes to a HuggingFace bucket.
* Local evaluation containers now default to Docker network mode `none`; use
  `--allow-network` only for an explicitly networked run. `--offline-deps-dir` mounts a
  sparse private cache store per instance, read-only on the host and copied to a writable
  grader-only location for both root and unprivileged test users inside the disposable
  container. Offline runs never fall back to
  downloading missing binary grading assets. Before applying a candidate patch, the
  evaluator rejects images containing known baked-in grading paths. Gold-only binary
  assets are enabled solely by the trusted `--gold` mode, never by prediction-file fields.
* `swebench eval --no-patch` runs baseline negative controls through the same evaluator
  and grading path as submitted and gold patches.
* `swebench images build --split <name>` limits a task-repository build to one split.
  `--reuse-images` now refuses missing local images instead of pulling registry fallbacks,
  verifies a build-input attestation, and creates containers by immutable image ID.
  Private dependency bundles require that explicit reuse mode and are bound to the image,
  reference patch, and dependency policy from which they were built.

Fixed:
* Evaluation scripts merge stderr into stdout before execution, and Mocha JSON parsers
  recover every complete reporter object from noisy logs. This prevents Docker/Podman
  stream batching from moving valid results outside their command trace.
* Non-UTF-8 bytes in a repository diff no longer abort an otherwise completed grade.
* Negative-control reports now distinguish an intentionally absent patch from a failed
  patch application, and run metadata cannot be overwritten with different network or
  input settings on resume.

## [5.0.1] - 8/17/2026

Fixed:
* A task's Dockerfile can `COPY` from its own `tasks/<instance_id>/` directory, so a task that needs a file at build time can carry it next to the Dockerfile that reads it. `ImageSpec` gained a `context_dir`, and `swebench.task.repo.task_paths` maps each instance to its build context.

## [5.0.0] - 8/17/2026

Breaking changes:
* Task repos hold one directory per instance under `tasks/`, and a `sweb.yaml` naming the dataset they publish. Task metadata is split by kind: `task.yaml` for the short fields, `tests.json` for FAIL_TO_PASS and PASS_TO_PASS, `problem_statement.md` and `hints.md` for prose. The harness reads that tree directly: `swebench dataset build|check|diff|push` and `swebench images build|check|push` all take a task repo path as their only argument, so a command can no longer be pointed at one dataset while fed another repo.
* `--assets_dir` is gone. Binary patch assets come from `tasks/<instance_id>/assets/`, and no longer need a url.
* Dataset aliases are now `full`, `verified`, `multilingual` and `multimodal`. Any other name, including a full HuggingFace id, is used as given.
* `prepare_images.main()` takes `task_repo` instead of `dataset_name` and `split`.
* `--dockerfile-repo` and `SWEBENCH_DOCKERFILE_REPOS` are gone; use `--task-repo`. `swebench.collect.build_local_datasets` is removed, since `swebench dataset build` compiles from a task repo.
* A task repo can publish several datasets: `sweb.yaml` names them all, each task lists the ones it belongs to, and `-d/--dataset` narrows any build, diff, push or image command. Verified and Lite are subsets of the same instances rather than copies of them.
* Task repo code moved into `swebench.task`: `swebench.task.repo`, `swebench.task.checks`, `swebench.task.publish`.
* Removed `swebench.constants`, which nothing imported.
* `swebench.versioning` moved out of this repo, to [swe-bench-tasks/src/versioning](https://github.com/SWE-bench/swe-bench-tasks/tree/main/src/versioning). It builds datasets rather than running them, and only works for the original Python repos. The `swebench dataset versions` command and seven `swebench.*` version helpers are gone with it.
* Names in the `swebench` namespace are now loaded on first use. Everything importable before still is, but `import swebench` no longer pulls in bs4, docker, datasets and modal.
* Datasets carry their own `eval_script` and metadata, so the harness no longer needs a Dockerfile repo checkout to evaluate.
* Image building moved to `swebench.image_builder`, with an `ImageSpec` that supports amd64 and arm64. `TestSpec` now assumes images already exist.
* Committed dataset parquets removed. HuggingFace is the source of truth.

Added:
* A run records the dataset and split it graded against, in `logs/run_evaluation/<run_id>/run.json`, so `swebench report <run_id>` no longer needs `-d`. Runs made before this still need it.
* A `swebench` CLI, with grouped commands and worked examples in the help text.
* SWE-bench Multimodal test-split support, including its log parsers and image assets. `--assets_dir` loads binary assets from disk when a URL has gone stale.

Fixed grading:
* A patch can no longer pass by printing its own `PASSED` lines. The eval script records the test command's exit code, and a log claiming no failures while the tests failed is not graded (#620).
* A run with no results and no sign the suite ran is rejected rather than scored as resolved.
* Infrastructure failures are labelled in the report, without being removed from the score (#586).
* Truncated parametrized test ids, skipped tests, results outside the output markers, and test names containing spaces are all handled.
* `report_dir` is honored; reports no longer land in the checkout.

## [4.1.0] - 9/11/2025
* #471 Fix git log leakage in environment images
* #427 Correct log parsing for patch application
* #463 Fix image removal for namespaces containing `/`
* #459 `instance_ids` are space separated, not comma separated
* #456 Extra validation for `make_run_report`
* Nicer logging for `run_evaluation`

## [4.0.1] - 5/6/2025
* #392 Support multilingual evaluation
* #358 Preserve all issue references sharing a keyword in PRs
* #390 Fix loading of jsonl data
* #370 Progress bar updates immediately when futures fail
* #369 Fix `prompt_col` generation in `create_text_dataset.py`

## [3.0.0] - 1/13/2025
* #285 SWE-bench Multimodal dev split
* #376 Fix missing text column
* #353 Clean diff after setup
* #366 Catch-all exception for docker pull
* #338 Fix logic error in old-style pytest parsing
* Paused support for SWE-bench task creation

## [2.0.12] - 7/21/2024
* Minor naming changes
* #186 fix: correct some typings and a incorrect function call
* #183 Fix timeout
* #178 Add schema version to report card
* #177 Fix run live scripts

## [2.0.9] - 7/10/2024
* #176 Move inference to swebench.inference sub-package
* #175 Fix link in collect README.md

## [2.0.8] - 7/8/2024
* Add `cutoff_date`, `max_pulls` arguments to collection pipeline
* Minor Django issue comment parsing logic
* Rewritten `extract_patches` logic
* Remove `MAP_REPO_TO_TEST_FRAMEWORK` symbol

## [2.0.4] - 7/5/2024
* #173 Fix: Allow to set GH token from env var in collect/print_pulls
* #171 Don't let tox install a virtualenv during evaluation
* #169 Handle failures because of None/empty patches

## [2.0.3] - 7/2/2024
* #149 Interface fix: run_id is required
* #151 Fix: Support JSON datasets (avoid loading json twice)
* #152 Add very simple CI
* #153 Various nitpicks
* #155 Fix link to collection tutorial
* #161 Fix path to image in docs
* #162 Fix evaluation hanging issue and improve patch apply
* #164 Fix so it doesn't crash when no env imgs to build
* #166 Fix newline outputs for django's log parser
* #168 Update reporting and skip empty model patch predictions

## [2.0.0] - 6/27/2024
Major release - the SWE-bench evaluation harness has been upgraded to incorporate containerized, sandboxed execution environments based on Docker. There are several chances to the API resulting from this:
* Removal of the `swebench.metrics` module
* Updates to the API of `swebench.harness` functionality
* Significant modifications to underlying evaluation logic
* Minor updates to installation specifications for different repos + versions.

Read the full report [here](https://github.com/swe-bench/SWE-bench/tree/main/docs/20240627_docker)

## [1.1.5] - 5/15/2024
* Add support for HumanEvalFix (Python, JS, Go, Java) ([source](https://huggingface.co/datasets/bigcode/humanevalpack))

## [1.1.0] - 4/15/2024
* Add `env_vars_test` field to allow for environment variable assignment for testing scripts.
* Change `pip_packages` installation specification to be a list instead of a string.
* Define PyPI package versioning explicitly for dev, test repos.
* Fix versioning for `astroid` dependency in `pylint` installation script`.
* Fix minor error in `parse_log_pytest_options`.
* Improve clarity + succinctness of logging.
* Make logging of subprocess args to log file smaller.
* Remove installation specifications for `dbt-core`, `transformers`.
* Remove redundant declaration of constants.
* Remove unused versions from installation specifications for dev, test repos.
* Rewrite `swebench.metrics.get_model_report`.

## [1.0.5] - 4/7/2024
* Fix log parsing for `pydicom`, `pylint`, and `requests` libraries. [5cb448](https://github.com/swe-bench/SWE-bench/commit/5cb448140a8cd05490650b0671d860765180f26c)

## [1.0.4] - 4/5/2024
* Fixed `env_list` parsing. [5be59d](https://github.com/swe-bench/SWE-bench/commit/5be59d665233ffb63b9beb30b2740cc41098e51f)
* Updated `ExecWrapper`, `LogWrapper` logic for harness. [231a2b](https://github.com/swe-bench/SWE-bench/commit/231a2b205c5ca9ddcb126b73b22667d79e1b6108)

## [1.0.2] - 4/2/2024
* Added `try/catch` around `lsof` based clean up for `run_evaluation.py`. [3fb217](https://github.com/swe-bench/SWE-bench/commit/3fb2179a5c69737465f916898e8708adffff9914)
* Fixed `get_eval_refs` function. [12a287](https://github.com/swe-bench/SWE-bench/commit/12a287a9591cb4a0d65483f0c8bfaa3375285bfc)
* Fixed `seaborn` log parser. [0372b6](https://github.com/swe-bench/SWE-bench/commit/0372b6a9ff62516067fb26f602163c231d818163)

## [1.0.1] - 3/31/2024
First working version. We strongly recommend not using versions older than this one.
* Added logging for failed installations. [58d24d](https://github.com/swe-bench/SWE-bench/commit/58d24d1b65b95ed96d57805604aca7adca49861d)
* Added missing `datasets` dependency. [68e89e](https://github.com/swe-bench/SWE-bench/commit/68e89ef8d099ca5c23a8fd5681e3f990cf729fd6)
* Reorganized repository to be directly build-able as a PyPI package. [548bdb](https://github.com/swe-bench/SWE-bench/commit/548bdbffb2ac5f0a09c1d7eb95bbee1bce126233)

## [0.6.9 - 0.6.9.2] - 3/31/2024 
> ⚠️ Do NOT use these versions. The PyPI package for these versions was under development. Specifically, some of the evaluation configurations required re-validation. A detailed report for the failures and our recovery from it are detailed in [Bug Report 4/5/2024](docs/reports/20240405_eval_bug/README.md).

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
