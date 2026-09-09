"""Is a task repo well formed?

The tree is the source of truth, so a malformed task is a broken instance later:
a missing eval.sh cannot be run, a split nobody registered never gets published,
an image name that disagrees with the convention pulls the wrong container.

`check` reports; `check --fix` writes back only what can be derived from the
tree itself, and never guesses at data it cannot see.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from swebench.task.repo import (
    AS_FILE,
    CONFIG_FILE,
    TASK_FILE,
    TEST_KEYS,
    TESTS_FILE,
    dump_yaml,
    load_config,
    load_yaml,
    task_dirs,
    tasks_root,
)

# kept in the tree but deliberately not published, e.g. instances that were dropped
DEPRECATED_SPLIT = "deprecated"

REQUIRED_FILES = (TASK_FILE, TESTS_FILE, "Dockerfile", *AS_FILE.values())
REQUIRED_KEYS = (
    "instance_id",
    "repo",
    "version",
    "base_commit",
    "split",
    "image",
    "log_parser",
    "eval_type",
)
# the eval script has to bracket its test output or grading cannot read the run
EVAL_MARKERS = (">>>>> Start Test Output", ">>>>> End Test Output")

CONDA_PROFILE = "/opt/miniconda3/etc/profile.d/conda.sh"
# the image has conda if it installs it, or inherits it from its base image
_INSTALLS_CONDA = re.compile(
    r"-p\s+/opt/miniconda3|conda\s+init|FROM\s+\S*conda", re.IGNORECASE
)
_GUARDED = re.compile(r"\[\s+-[fs]\s|test\s+-[fs]\s")


@dataclass
class Problem:
    where: str
    message: str
    fixable: bool = False
    # errors stop a publish; warnings are reported and do not
    severity: str = "error"

    def __str__(self) -> str:
        return f"{self.severity}: {self.where}: {self.message}"


def errors(problems: list[Problem]) -> list[Problem]:
    return [p for p in problems if p.severity == "error"]


def expected_image(instance_id: str, namespace: str = "swebench") -> str:
    """The image name the harness derives for an instance."""
    key = f"sweb.eval.x86_64.{instance_id}:latest".lower()
    return f"{namespace}/{key}".replace("__", "_1776_")


def _bashrc_problem(dockerfile: str) -> str | None:
    """A .bashrc this image cannot read without printing an error.

    Sourcing a conda profile the image never installs puts that error on line 0
    of every shell, and the activation the line exists to perform never happens.
    """
    if _INSTALLS_CONDA.search(dockerfile):
        return None
    for line in dockerfile.splitlines():
        if CONDA_PROFILE in line and ".bashrc" in line and not _GUARDED.search(line):
            return (
                f"Dockerfile writes a .bashrc sourcing {CONDA_PROFILE}, which this "
                f"image never installs: every shell prints an error before its own "
                f"output. Guard it with [ -f {CONDA_PROFILE} ] && ..."
            )
    return None


def _check_task(
    task_dir: Path, known_splits: set[str], known_datasets: set[str]
) -> list[Problem]:
    problems = []
    where = f"tasks/{task_dir.name}"

    missing = [f for f in REQUIRED_FILES if not (task_dir / f).is_file()]
    if missing:
        problems.append(Problem(where, f"missing {', '.join(sorted(missing))}"))
    if not (task_dir / TASK_FILE).is_file():
        return problems  # nothing further can be checked

    try:
        meta = load_yaml(task_dir / TASK_FILE)
    except yaml.YAMLError as e:
        return [*problems, Problem(where, f"{TASK_FILE} is not valid YAML: {e}")]

    for key in REQUIRED_KEYS:
        if key not in meta:
            problems.append(Problem(where, f"{TASK_FILE} has no {key}"))
    if meta.get("instance_id") not in (None, task_dir.name):
        problems.append(
            Problem(where, f"{TASK_FILE} instance_id is {meta['instance_id']!r}")
        )
    tests_path = task_dir / TESTS_FILE
    if tests_path.is_file():
        try:
            tests = json.loads(tests_path.read_text())
        except json.JSONDecodeError as e:
            return [*problems, Problem(where, f"{TESTS_FILE} is not valid JSON: {e}")]
        for key in TEST_KEYS:
            if key not in tests:
                problems.append(Problem(where, f"{TESTS_FILE} has no {key}"))
            elif not isinstance(tests[key], list):
                problems.append(
                    Problem(where, f"{key} is {type(tests[key]).__name__}, not a list")
                )
            elif not all(isinstance(t, str) for t in tests[key]):
                problems.append(
                    Problem(where, f"{key} holds something that is not a string")
                )
        if tests.get(TEST_KEYS[0]) == [] and meta.get("split") != DEPRECATED_SPLIT:
            problems.append(
                Problem(where, "no FAIL_TO_PASS, so nothing grades this task")
            )

    claimed = meta.get("datasets")
    if not claimed and meta.get("split") != DEPRECATED_SPLIT:
        problems.append(
            Problem(where, f"{TASK_FILE} does not say which datasets it belongs to")
        )
    elif not isinstance(claimed, list):
        problems.append(Problem(where, "datasets is not a list"))
    else:
        unknown = sorted(set(claimed) - known_datasets)
        if unknown:
            problems.append(
                Problem(where, f"datasets not published by {CONFIG_FILE}: {' '.join(unknown)}")
            )

    split = meta.get("split")
    if split is not None and split not in known_splits | {DEPRECATED_SPLIT}:
        problems.append(
            Problem(where, f"split {split!r} is not in {CONFIG_FILE}", fixable=True)
        )
    if "image" in meta and meta["image"] != expected_image(task_dir.name):
        problems.append(
            Problem(
                where, f"image {meta['image']!r} is not the derived name", fixable=True
            )
        )

    if (task_dir / "eval.sh").is_file():
        script = (task_dir / "eval.sh").read_text()
        for marker in EVAL_MARKERS:
            if marker not in script:
                problems.append(Problem(where, f"eval.sh has no {marker!r} marker"))
    dockerfile = task_dir / "Dockerfile"
    if dockerfile.is_file():
        message = _bashrc_problem(dockerfile.read_text(errors="replace"))
        if message:
            problems.append(Problem(where, message, severity="warning"))
    for name in ("gold.patch", "test.patch"):
        path = task_dir / name
        if (
            path.is_file()
            and path.stat().st_size
            and "diff --git" not in path.read_text(errors="replace")
        ):
            problems.append(Problem(where, f"{name} does not look like a diff"))
    return problems


def check_task_repo(repo_path: str | Path, fix: bool = False) -> list[Problem]:
    """Every problem found, in reporting order. With fix, repair the fixable ones."""
    repo_path = Path(repo_path)
    problems: list[Problem] = []

    try:
        config = load_config(repo_path)
        known_splits = set(config["splits"])
        known_datasets = set(config["datasets"])
    except (FileNotFoundError, ValueError) as e:
        return [Problem(CONFIG_FILE, str(e))]

    try:
        dirs = task_dirs(repo_path)
    except FileNotFoundError as e:
        return [Problem("tasks/", str(e))]
    if not dirs:
        return [Problem("tasks/", "no task directories")]

    for task_dir in dirs:
        problems.extend(_check_task(task_dir, known_splits, known_datasets))

    # splits are derivable from the tree, so an unregistered one can be filled in
    if fix:
        used = {
            load_yaml(d / TASK_FILE).get("split")
            for d in dirs
            if (d / TASK_FILE).is_file()
        }
        publishable = sorted(s for s in used if s and s != DEPRECATED_SPLIT)
        if publishable and publishable != sorted(known_splits):
            config["splits"] = publishable
            (repo_path / CONFIG_FILE).write_text(dump_yaml(config))
            problems = [
                p for p in problems if not (p.fixable and CONFIG_FILE in p.message)
            ]
        for task_dir in dirs:
            meta_path = task_dir / TASK_FILE
            if not meta_path.is_file():
                continue
            meta = load_yaml(meta_path)
            derived = expected_image(task_dir.name)
            if meta.get("image") != derived:
                meta["image"] = derived
                meta_path.write_text(dump_yaml(meta))
                problems = [
                    p
                    for p in problems
                    if not (
                        p.fixable
                        and p.where.endswith(task_dir.name)
                        and "image" in p.message
                    )
                ]

    # an eval card is published under the name of its dataset, so one named
    # anything else is a card that silently never reaches a dataset
    published = {d.split("/")[-1] for d in known_datasets}
    eval_dir = repo_path / "eval"
    if eval_dir.is_dir():
        problems.extend(
            Problem(
                f"eval/{path.name}",
                f"no dataset named {path.stem} in {CONFIG_FILE}, so it is not published",
                severity="warning",
            )
            for path in sorted(eval_dir.glob("*.yaml"))
            if path.stem not in published
        )

    # a directory with no task.yaml is invisible to the loaders, so say so
    strays = [
        d.name
        for d in tasks_root(repo_path).iterdir()
        if d.is_dir() and not (d / TASK_FILE).is_file()
    ]
    problems.extend(
        Problem(f"tasks/{name}", f"no {TASK_FILE}, so it is not a task")
        for name in strays
    )
    return problems
