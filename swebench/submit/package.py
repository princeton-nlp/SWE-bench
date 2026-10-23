"""Turn a finished evaluation run into a leaderboard submission.

A submission is two trees, because the heavy artifacts and the leaderboard entry live
in different places:

    submission-repo/        the submitter's own public GitHub repo
      all_preds.jsonl
      logs/<iid>/{patch.diff,report.json,test_output.txt[.gz]}
      trajs/<iid>.*
    entry/                  the PR to github.com/SWE-bench/experiments
      metadata.yaml
      README.md
      results/{results.json,resolved_by_repo.json,resolved_by_time.json}
      per_instance_details.json    (multilingual)

``logs/`` mirrors what the S3 bucket has always held, so existing consumers
(``analysis/download_logs.py``, the site's log links) keep working against a repo.

Resolution is **re-derived** here, never read from the run's own ``report.json``: each
instance is re-graded from its ``test_output.txt`` against the dataset, the same way
``experiments/analysis/get_results.py`` has always done it. A submission that ships a
doctored report still scores from its logs.
"""

import gzip
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from swebench.harness.constants import (
    LOG_REPORT,
    LOG_RUN_METADATA,
    LOG_TEST_OUTPUT,
    RUN_EVALUATION_LOG_DIR,
)

# Directory name under experiments/evaluation/ -> the dataset it is scored against.
# `bash-only` is deliberately absent: those submissions now live under `verified`, with
# the harness identified by metadata tags rather than by a separate directory.
SPLIT_DATASETS = {
    "lite": "SWE-bench/SWE-bench_Lite",
    "verified": "SWE-bench/SWE-bench_Verified",
    "test": "SWE-bench/SWE-bench",
    "multilingual": "SWE-bench/SWE-bench_Multilingual",
    "multimodal": "SWE-bench/SWE-bench_Multimodal",
}

# Multimodal is evaluated through sb-cli, which produces no local logs or trajectories,
# so there is nothing for a submission repo to hold -- only the entry is built.
ENTRY_ONLY_SPLITS = {"multimodal"}

# GitHub warns above 50MB per file and rejects above 100MB. Test output is the only
# artifact that gets anywhere near it (verbose JS runners produce tens of MB), so it is
# gzipped, and anything still over this after compression is refused rather than left
# for `git push` to reject.
MAX_ARTIFACT_BYTES = 50 * 1024 * 1024


@dataclass
class PackageResult:
    split: str
    submission_id: str
    out_dir: Path
    model: str = ""
    resolved: list[str] = field(default_factory=list)
    no_generation: list[str] = field(default_factory=list)
    no_logs: list[str] = field(default_factory=list)
    oversized: list[str] = field(default_factory=list)
    n_trajs: int = 0
    kept: list[str] = field(default_factory=list)  # existing files left alone

    @property
    def n_scored(self) -> int:
        return len(self.resolved)


class PackageError(RuntimeError):
    pass


def submission_id(model_name: str, when: Optional[datetime] = None) -> str:
    """``20260901_myagent`` -- the folder name experiments expects."""
    stamp = (when or datetime.now()).strftime("%Y%m%d")
    slug = model_name.replace("/", "__").replace(" ", "-")
    return f"{stamp}_{slug}"


SUBMISSION_META = "submission.json"


def write_submission_meta(
    out_dir: Path, result: "PackageResult", run_dir: Path
) -> Path:
    """Record what `package` derived, so publish/register/verify need not re-derive it.

    Written beside the two trees rather than inside entry/, which is committed to
    experiments verbatim.
    """
    path = Path(out_dir) / SUBMISSION_META
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "submission_id": result.submission_id,
                "split": result.split,
                "model": result.model,
                "run_dir": str(run_dir),
            },
            indent=2,
        )
    )
    return path


def read_submission_meta(out_dir: Path) -> dict:
    """What `package` recorded for this submission, or {} if it is not there."""
    path = Path(out_dir) / SUBMISSION_META
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text()) or {}
    except json.JSONDecodeError:
        return {}


SUBMISSION_DIR = "submission"


def resolve_submission_dir(path: Path) -> Path:
    """The submission directory, given a run directory or the submission itself.

    Every `submit` command accepts ``logs/evaluation/<run_id>`` so one path works for
    the whole flow; pointing straight at the submission still works.
    """
    path = Path(path)
    for candidate in (path, path / SUBMISSION_DIR):
        if (candidate / "entry").is_dir():
            return candidate
    raise PackageError(
        f"no submission under {path.resolve()} -- looked for entry/ and "
        f"{SUBMISSION_DIR}/entry/. Run `swebench submit package` first."
    )


def resolve_entry_dir(path: Path) -> Path:
    """The entry directory, given a run directory, a submission, or the entry itself.

    The third form is how an entry already committed to experiments is checked.
    """
    path = Path(path)
    for candidate in (path, path / "entry", path / SUBMISSION_DIR / "entry"):
        if (candidate / "metadata.yaml").is_file():
            return candidate
    raise PackageError(
        f"no submission entry under {path.resolve()} -- looked for metadata.yaml here, "
        f"in entry/, and in {SUBMISSION_DIR}/entry/."
    )


def resolve_run(run: str) -> tuple[str, Path]:
    """A run id and its directory, from either a path or a bare run id."""
    path = Path(run)
    if path.is_dir():
        return path.name, path
    return run, RUN_EVALUATION_LOG_DIR / run


def _is_instance_dir(path: Path) -> bool:
    """An instance directory is one the harness wrote artifacts into."""
    return path.is_dir() and any(
        (path / name).is_file() for name in ("patch.diff", LOG_REPORT, LOG_TEST_OUTPUT)
    )


@dataclass
class ResolvedRun:
    run_dir: Path  # logs/evaluation/<run_id>
    logs_dir: Path  # <run_dir>/<model>, holding one directory per instance
    model: str


def resolve_run_dir(run_path: Path, model: Optional[str] = None) -> ResolvedRun:
    """Locate a run's per-instance artifacts and the model that produced them.

    Accepts either a run directory (``logs/evaluation/<run_id>``) or the model
    directory inside it, so tab-completing to either depth works.
    """
    run_path = Path(run_path)
    if not run_path.is_dir():
        raise PackageError(f"no such run directory: {run_path.resolve()}")

    if any(_is_instance_dir(d) for d in run_path.iterdir()):
        return ResolvedRun(run_path.parent, run_path, model or run_path.name)

    # A model directory is one that holds instance directories. Identifying them
    # structurally rather than by "any subdirectory" means unrelated directories --
    # including this command's own default output -- are simply not candidates.
    models = sorted(
        d.name
        for d in run_path.iterdir()
        if d.is_dir() and any(_is_instance_dir(c) for c in d.iterdir())
    )
    if not models:
        raise PackageError(
            f"{run_path.resolve()} holds no evaluation artifacts -- is this a run directory?"
        )
    if model:
        if model.replace("/", "__") not in models:
            raise PackageError(
                f"no model {model!r} in {run_path.resolve()} (have: {', '.join(models)})"
            )
        return ResolvedRun(run_path, run_path / model.replace("/", "__"), model)
    if len(models) > 1:
        raise PackageError(
            f"{run_path.resolve()} holds several models ({', '.join(models)}); "
            "pass --model to pick one"
        )
    return ResolvedRun(run_path, run_path / models[0], models[0])


# Dataset id -> the experiments/evaluation/ directory name it is submitted under.
_DATASET_SPLITS = {v.lower(): k for k, v in SPLIT_DATASETS.items()}


def split_from_run(run_dir: Path) -> Optional[str]:
    """The leaderboard split a run scored against, from the metadata it recorded."""
    meta_path = run_dir / LOG_RUN_METADATA
    if not meta_path.is_file():
        return None
    dataset = (json.loads(meta_path.read_text()) or {}).get("dataset") or ""
    return _DATASET_SPLITS.get(dataset.strip().lower())


def load_predictions(path: Path) -> dict[str, dict]:
    """Read a .json or .jsonl predictions file into {instance_id: prediction}."""
    text = path.read_text()
    if path.suffix == ".jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        loaded = json.loads(text)
        rows = list(loaded.values()) if isinstance(loaded, dict) else loaded
    return {r["instance_id"]: r for r in rows}


def _copy_artifact(src: Path, dest_dir: Path, oversized: list[str], iid: str) -> None:
    """Copy one artifact, gzipping test output and refusing what is still too large."""
    if src.name == LOG_TEST_OUTPUT:
        dest = dest_dir / f"{LOG_TEST_OUTPUT}.gz"
        with src.open("rb") as fin, gzip.open(dest, "wb") as fout:
            shutil.copyfileobj(fin, fout)
        if dest.stat().st_size > MAX_ARTIFACT_BYTES:
            size_mb = dest.stat().st_size / 1024 / 1024
            dest.unlink()
            oversized.append(f"{iid} ({size_mb:.0f}MB gzipped)")
        return
    shutil.copy2(src, dest_dir / src.name)


def _grade(
    instance: dict, patch_path: Path, test_output_path: Path, model: str
) -> bool:
    """Re-derive one instance's verdict from its own test output.

    Deliberately ignores the run's report.json -- the log is the evidence, and grading
    it here is what lets anyone re-check a submission without trusting the submitter.
    """
    from swebench.harness.grading import get_eval_report
    from swebench.harness.utils import make_test_spec

    prediction = {
        "instance_id": instance["instance_id"],
        "model_patch": patch_path.read_text(),
        "model_name_or_path": model,
    }
    report = get_eval_report(
        make_test_spec(instance),
        prediction=prediction,
        test_log_path=str(test_output_path),
        include_tests_status=False,
    )
    return bool(report[instance["instance_id"]]["resolved"])


def _year(instance: dict) -> Optional[int]:
    created = instance.get("created_at")
    if not created:
        return None
    try:
        return datetime.fromisoformat(str(created).rstrip("Z")).year
    except ValueError:
        return None


def package_run(
    run_path: Path,
    split: Optional[str] = None,
    out_dir: Optional[Path] = None,
    *,
    model: Optional[str] = None,
    predictions: Optional[Path] = None,
    trajs: Optional[Path] = None,
    sub_id: Optional[str] = None,
) -> PackageResult:
    """Build the submission-repo/ and entry/ trees for one evaluated run.

    ``split`` and ``out_dir`` are derived from the run when not given: the split from
    the dataset the run recorded, and the output from a ``submission/`` directory beside
    the run's artifacts.
    """
    resolved = resolve_run_dir(run_path, model)
    logs_root, model = resolved.logs_dir, resolved.model

    if split is None:
        split = split_from_run(resolved.run_dir)
        if split is None:
            raise PackageError(
                f"{resolved.run_dir.resolve()} does not record which dataset it used, "
                "so pass --split"
            )
    if split not in SPLIT_DATASETS:
        raise PackageError(
            f"unknown split {split!r}; expected one of {', '.join(sorted(SPLIT_DATASETS))}"
        )
    out_dir = (
        Path(out_dir) if out_dir is not None else resolved.run_dir / SUBMISSION_DIR
    )

    from datasets import load_dataset

    instances = {
        i["instance_id"]: i for i in load_dataset(SPLIT_DATASETS[split], split="test")
    }

    preds = load_predictions(predictions) if predictions else {}
    result = PackageResult(
        split=split,
        submission_id=sub_id or submission_id(model),
        out_dir=out_dir,
        model=model,
    )
    entry = result.out_dir / "entry"
    (entry / "results").mkdir(parents=True, exist_ok=True)
    repo_dir = result.out_dir / "submission-repo"
    entry_only = split in ENTRY_ONLY_SPLITS
    if not entry_only:
        (repo_dir / "logs").mkdir(parents=True, exist_ok=True)

    by_repo: dict[str, dict[str, int]] = {}
    by_year: dict[int, dict[str, int]] = {}

    for iid, instance in sorted(instances.items()):
        bucket_repo = by_repo.setdefault(
            instance.get("repo", "?"), {"resolved": 0, "total": 0}
        )
        bucket_repo["total"] += 1
        if (year := _year(instance)) is not None:
            bucket_year = by_year.setdefault(year, {"resolved": 0, "total": 0})
            bucket_year["total"] += 1

        inst_logs = logs_root / iid
        patch_path, output_path = inst_logs / "patch.diff", inst_logs / LOG_TEST_OUTPUT
        if not inst_logs.is_dir() or not patch_path.is_file():
            result.no_generation.append(iid)
            continue
        if not output_path.is_file():
            result.no_logs.append(iid)
            continue

        if _grade(instance, patch_path, output_path, model):
            result.resolved.append(iid)
            bucket_repo["resolved"] += 1
            if year is not None:
                by_year[year]["resolved"] += 1

        if entry_only:
            continue
        dest = repo_dir / "logs" / iid
        dest.mkdir(parents=True, exist_ok=True)
        for artifact in (patch_path, inst_logs / LOG_REPORT, output_path):
            if artifact.is_file():
                _copy_artifact(artifact, dest, result.oversized, iid)

    if result.oversized:
        raise PackageError(
            "these instances' test output is too large to host in a git repo even "
            f"gzipped (>{MAX_ARTIFACT_BYTES // 1024 // 1024}MB): "
            + ", ".join(result.oversized)
        )

    (entry / "results" / "results.json").write_text(
        json.dumps(
            {
                "no_generation": sorted(result.no_generation),
                "no_logs": sorted(result.no_logs),
                "resolved": sorted(result.resolved),
            },
            indent=4,
        )
    )
    (entry / "results" / "resolved_by_repo.json").write_text(
        json.dumps(dict(sorted(by_repo.items())), indent=4)
    )
    (entry / "results" / "resolved_by_time.json").write_text(
        json.dumps({str(k): v for k, v in sorted(by_year.items())}, indent=4)
    )
    # metadata.yaml and README.md are filled in by hand, and publish writes the assets
    # block into the first. Regenerating either would throw that away, so they are only
    # created when absent. Everything else is derived and always rewritten.
    for name, content in (
        ("metadata.yaml", lambda: _metadata_stub(result, model)),
        ("README.md", lambda: _readme_stub(result, model, len(instances))),
    ):
        if (entry / name).exists():
            result.kept.append(name)
        else:
            (entry / name).write_text(content())

    write_submission_meta(out_dir, result, resolved.run_dir)

    if not entry_only:
        _write_predictions(repo_dir, preds, logs_root, model, instances)
        if trajs:
            result.n_trajs = _copy_trajs(
                Path(trajs), repo_dir / "trajs", set(instances)
            )

    return result


def _write_predictions(
    repo_dir: Path, preds: dict[str, dict], logs_root: Path, model: str, instances: dict
) -> None:
    """Write all_preds.jsonl -- from the predictions file if given, else rebuilt from
    each instance's patch.diff so a submission repo always carries its predictions."""
    rows = []
    for iid in sorted(instances):
        if iid in preds:
            rows.append(preds[iid])
            continue
        patch = logs_root / iid / "patch.diff"
        if patch.is_file():
            rows.append(
                {
                    "instance_id": iid,
                    "model_name_or_path": model,
                    "model_patch": patch.read_text(),
                }
            )
    (repo_dir / "all_preds.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows)
    )


def _copy_trajs(src: Path, dest: Path, instance_ids: set[str]) -> int:
    """Copy per-instance reasoning traces, flattening <iid>/<iid>.traj.json to
    trajs/<iid>.traj.json as the leaderboard expects. Returns the number copied.

    Only files named after a known instance are taken: an agent's output directory also
    holds run-level files (mini-SWE-agent leaves preds.json and its own log there),
    which are not reasoning traces.
    """
    if not src.is_dir():
        raise PackageError(f"--trajs {src} is not a directory")
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in sorted(src.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        # <iid>/<iid>.traj.json -> <iid>.traj.json; a flat file keeps its own name
        name = (
            path.name
            if path.parent == src
            else f"{path.parent.name}{''.join(path.suffixes)}"
        )
        if not any(name == iid or name.startswith(f"{iid}.") for iid in instance_ids):
            continue
        shutil.copy2(path, dest / name)
        copied += 1
    return copied


def _metadata_stub(result: PackageResult, model: str) -> str:
    """metadata.yaml with everything derivable filled in and the rest left as TODO.

    `assets` is written by `publish`, once the submission repo has a URL.
    """
    meta = {
        "info": {
            "name": "TODO leaderboard entry name",
            "site": "TODO url describing the system",
            "report": "TODO arXiv / technical report / blog post",
            "authors": "TODO",
            "logo": "TODO url, and commit the image as logo.png in this folder",
        },
        "tags": {
            "checked": False,
            "model": [model],
            "org": "TODO",
            "os_model": False,
            "os_system": False,
            "system": {"attempts": 1},
            "agent": "TODO harness name, without a version",
            "agent_org": "TODO who publishes the agent",
            "model_display": "TODO model as you want it written, no date suffix",
            "model_org": "TODO who publishes the model",
        },
    }
    header = (
        f"# Generated by `swebench submit package` for {result.submission_id}\n"
        f"# Scored {len(result.resolved)} resolved on the {result.split} split.\n"
        "# Replace every TODO before opening the PR; see experiments/checklist.md.\n"
        "# `assets` is added by `swebench submit publish`.\n"
    )
    return header + yaml.safe_dump(meta, sort_keys=False)


def _readme_stub(result: PackageResult, model: str, n_total: int) -> str:
    pct = 100.0 * len(result.resolved) / n_total if n_total else 0.0
    return f"""# {result.submission_id}

TODO: describe the system, and link the technical report.

| | |
| --- | --- |
| Split | `{result.split}` |
| Model | `{model}` |
| Resolved | {len(result.resolved)} / {n_total} ({pct:.2f}%) |
| No generation | {len(result.no_generation)} |
| Missing logs | {len(result.no_logs)} |

Resolution was re-derived from each instance's `test_output.txt` by
`swebench submit package`, not taken from the run's own report.
"""
