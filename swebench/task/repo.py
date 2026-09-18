"""Reading a task repo, the source of truth for a dataset's instances.

A task repo holds one directory per instance::

    sweb.yaml             the datasets this repo publishes, and their splits
    tasks/<instance_id>/
        task.yaml             short metadata, including which split the task is in
        tests.json            the tests that decide whether a patch resolved it
        problem_statement.md  the issue text shown to a model
        hints.md              discussion from the issue, absent when there is none
        gold.patch            the reference fix
        test.patch            the tests that grade it
        eval.sh               the script the harness runs
        Dockerfile            the image it runs in
        test_assets/          binary files a patch cannot carry, staged at eval time
        problem_assets/       what the problem statement links to, archived so it
                              cannot rot; the harness never reads these

Nothing here consults HuggingFace: a task repo can rebuild its dataset alone,
which is what makes local development of a new dataset possible.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

TASKS_SUBDIR = "tasks"
ASSETS_SUBDIR = "test_assets"

# dataset columns kept as their own file rather than inside task.yaml
AS_FILE = {
    "patch": "gold.patch",
    "test_patch": "test.patch",
    "eval_script": "eval.sh",
    "problem_statement": "problem_statement.md",
}
# written only when non-empty, so an empty file never stands in for missing prose
OPTIONAL_FILE = {"hints_text": "hints.md"}
# JSON rather than YAML: these are arbitrary strings, sometimes pasted in by hand,
# and JSON has no implicit typing to turn `no` or `1.0` into something else
TESTS_FILE = "tests.json"


class UnknownDataset(KeyError):
    """Asked for a dataset the repo does not publish."""

    def __str__(self) -> str:  # KeyError quotes its message otherwise
        return self.args[0]


TEST_KEYS = ("FAIL_TO_PASS", "PASS_TO_PASS")
CONFIG_FILE = "sweb.yaml"
TASK_FILE = "task.yaml"


class _Dumper(yaml.SafeDumper):
    """Writes multi-line strings as literal blocks, so they stay readable."""


def _represent_str(dumper: yaml.SafeDumper, data: str):
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_Dumper.add_representer(str, _represent_str)


def dump_yaml(data: dict) -> str:
    return yaml.dump(
        data,
        Dumper=_Dumper,
        sort_keys=True,
        allow_unicode=True,
        default_flow_style=False,
    )


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _read(path: Path) -> str:
    # newline="" so CRLF inside a patch survives verbatim
    with open(path, newline="") as fh:
        return fh.read()


def tasks_root(repo_path: str | Path) -> Path:
    root = Path(repo_path) / TASKS_SUBDIR
    if not root.is_dir():
        raise FileNotFoundError(f"{repo_path} has no {TASKS_SUBDIR}/ directory")
    return root


def task_dirs(repo_path: str | Path) -> list[Path]:
    return sorted(
        d for d in tasks_root(repo_path).iterdir() if (d / TASK_FILE).exists()
    )


def dump_tests(tests: dict) -> str:
    return json.dumps(tests, indent=2, ensure_ascii=False) + "\n"


def load_task(task_dir: str | Path) -> dict:
    """One task directory, as the instance dict the harness expects."""
    task_dir = Path(task_dir)
    instance = load_yaml(task_dir / TASK_FILE)
    for column, filename in AS_FILE.items():
        instance[column] = _read(task_dir / filename)
    for column, filename in OPTIONAL_FILE.items():
        path = task_dir / filename
        instance[column] = _read(path) if path.is_file() else ""
    instance.update(json.loads((task_dir / TESTS_FILE).read_text()))
    return instance


def load_task_repo(
    repo_path: str | Path, instance_ids: list[str] | None = None
) -> list[dict]:
    """Every instance in the repo, or just the ones asked for.

    Unknown ids are an error rather than a silent omission: a typo should not
    quietly shrink the run.
    """
    dirs = task_dirs(repo_path)
    if instance_ids is None:
        return [load_task(d) for d in dirs]

    by_id = {d.name: d for d in dirs}
    missing = sorted(set(instance_ids) - set(by_id))
    if missing:
        raise KeyError(f"not in {tasks_root(repo_path)}: {' '.join(missing)}")
    return [load_task(by_id[i]) for i in instance_ids]


def load_dockerfiles(
    repo_path: str | Path, instance_ids: list[str] | None = None
) -> dict[str, str]:
    """instance_id -> Dockerfile contents."""
    dirs = task_dirs(repo_path)
    if instance_ids is not None:
        wanted = set(instance_ids)
        dirs = [d for d in dirs if d.name in wanted]
    return {d.name: (d / "Dockerfile").read_text() for d in dirs}


def task_paths(
    repo_path: str | Path, instance_ids: list[str] | None = None
) -> dict[str, Path]:
    """instance_id -> its task directory, which is its Dockerfile's build context.

    A Dockerfile in a task repo can `COPY` from its own task directory, so a task
    that needs a file at build time -- a patch too large to inline, say -- can
    carry it next to the Dockerfile that reads it.
    """
    dirs = task_dirs(repo_path)
    if instance_ids is not None:
        wanted = set(instance_ids)
        dirs = [d for d in dirs if d.name in wanted]
    return {d.name: d for d in dirs}


def asset_path(repo_path: str | Path, instance_id: str, path: str) -> Path:
    """Where a staged asset lives: tasks/<id>/test_assets/<path in the repo>."""
    if Path(instance_id).name != instance_id or instance_id in {"", ".", ".."}:
        raise ValueError(f"Unsafe instance ID for asset lookup: {instance_id!r}")
    root = (tasks_root(repo_path) / instance_id / ASSETS_SUBDIR).resolve()
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError(
            f"Asset path for {instance_id} escapes its test_assets directory: {path!r}"
        ) from error
    return candidate


def load_config(repo_path: str | Path) -> dict:
    """The repo's own description of what it publishes.

    Keeps the destination with the data, so a command cannot be pointed at the
    wrong dataset by mistake.
    """
    path = Path(repo_path) / CONFIG_FILE
    if not path.is_file():
        raise FileNotFoundError(f"{repo_path} has no {CONFIG_FILE}")
    config = load_yaml(path)
    if not config.get("datasets"):
        raise ValueError(f"{path} does not name any datasets")
    config.setdefault("splits", ["test"])
    return config


def published_tasks(
    repo_path: str | Path, datasets: list[str] | None = None
) -> dict[str, dict[str, list[dict]]]:
    """Instances grouped by dataset, then by split.

    A task names the datasets it belongs to, because subsets like Verified and
    Lite are drawn from the same instances: one copy of the data, many datasets.
    A task in an unpublished split (deprecated, say) stays in the tree and can
    still be built by id, but never reaches a dataset.
    """
    config = load_config(repo_path)
    wanted = set(datasets or config["datasets"])
    unknown = wanted - set(config["datasets"])
    if unknown:
        raise UnknownDataset(
            f"{Path(repo_path) / CONFIG_FILE} does not publish "
            f"{' '.join(sorted(unknown))}. It publishes: "
            f"{' '.join(config['datasets'])}"
        )
    splits = set(config["splits"])

    grouped: dict[str, dict[str, list[dict]]] = {d: {} for d in sorted(wanted)}
    for instance in load_task_repo(repo_path):
        split = instance.get("split")
        if split not in splits:
            continue
        for dataset in set(instance.get("datasets") or []) & wanted:
            grouped[dataset].setdefault(split, []).append(instance)
    return grouped


def select_tasks(
    repo_path: str | Path,
    instance_ids: list[str] | None = None,
    datasets: list[str] | None = None,
) -> list[dict]:
    """The tasks a command should act on.

    With ids, exactly those, from any split, so an instance being repaired can
    be named even while it sits in an unpublished split. Without ids, only what
    the repo publishes, so deprecated tasks are not built or pushed by default.
    """
    if instance_ids:
        return load_task_repo(repo_path, instance_ids)
    # an instance can belong to several datasets, so keep one copy of each
    seen: dict[str, dict] = {}
    for by_split in published_tasks(repo_path, datasets).values():
        for instances in by_split.values():
            for instance in instances:
                seen.setdefault(instance["instance_id"], instance)
    return [seen[i] for i in sorted(seen)]
