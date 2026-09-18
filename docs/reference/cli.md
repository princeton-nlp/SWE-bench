# Command line interface

Installing the package provides a `swebench` command. Every command takes
`-h/--help`, and the top level takes `-v/--verbose`.

`DATASET` accepts an alias, a HuggingFace id, or a local path:

| alias | dataset |
|---|---|
| `full` | `SWE-bench/SWE-bench` |
| `lite` | `SWE-bench/SWE-bench_Lite` |
| `verified` | `SWE-bench/SWE-bench_Verified` |
| `multimodal` | `SWE-bench/SWE-bench_Multimodal` |
| `multilingual` | `SWE-bench/SWE-bench_Multilingual` |

## Evaluate

### `swebench infer DATASET`

Generate predictions with [mini-SWE-agent](https://mini-swe-agent.com). Writes
`preds.json` and one trajectory per instance to `logs/inference/<run_id>`.

A thin wrapper around `mini-extra swebench`. It resolves SWE-bench dataset aliases and
passes mini's bundled config, which mini drops as soon as you give any `-c`. Unknown
arguments go straight through, so `--filter` and `--slice` work as documented there.

```bash
swebench infer verified -m gpt-5 --run-id gpt5 -w 8
swebench infer verified -c model.yaml --run-id g35flash -w 12
```

Use `--python /path/to/venv/bin/python` if mini lives in another environment.

Keys are mini's business: export what the provider reads. Note that
`api_key: os.environ/VAR` in a model config is sent as that literal string, not
resolved. Set the real variable instead (`OPENAI_API_KEY` for OpenAI-compatible
endpoints).

### `swebench eval DATASET`

Run the reference patches or a model's predictions.

```bash
swebench eval verified --gold
swebench eval multimodal --no-patch --task-repo ~/swe-bench-multimodal-tasks \
  --run-id baseline
swebench eval verified -p preds.jsonl --run-id gpt5 -j 16
swebench eval multimodal --gold --task-repo ~/swe-bench-multimodal-tasks \
  -i carbon-design-system__carbon-10188
swebench eval full --gold --modal
```

Pass exactly one of `--gold`, `--no-patch`, or `-p/--predictions`. `--no-patch`
runs the pristine repository as a negative control. `-i/--instance` is repeatable,
`-j/--workers` sets parallelism, `-t/--timeout` is per instance (1800s).

Local evaluation containers have no network by default. `--allow-network` opts into
Docker's normal network. For patches that change dependency manifests, pass a private
cache root with `--offline-deps-dir`; a directory named for the selected instance is
mounted read-only and copied into the disposable grader as
`/run/swebench-offline/{npm,yarn}`. The cache is not present in solver-visible images.
When a task repo declares a required bundle, it must be supplied even with
`--allow-network`; task evaluation scripts may independently enforce offline package
manager mode.
When grading from a task checkout, pass `--task-repo` so binary test fixtures are read
from its local `test_assets/` mirror instead of requiring their original URLs.
Offline evaluation intentionally treats a missing local fixture as an infrastructure
error. Legacy URL-only evaluation requires the explicit `--allow-network` opt-in, which
also gives the grader container network access.
Build images first, then create dependency bundles from those exact images; evaluation
with `--offline-deps-dir` therefore also requires `--reuse-images`.

Artifacts go to `logs/evaluation/<run_id>/`, the summary to its `results.json`.
That path is relative to where you run the command.
Re-running a run id skips instances that already have a `report.json`.

### `swebench report RUN_ID`

Recompute verdicts from a finished run's saved logs, without starting containers.
Useful after a log-parser fix, since the test output is already on disk.

The dataset comes from the run itself, recorded at evaluation time in
`logs/evaluation/<run_id>/run.json`. Pass `-d` for older runs, or to grade against a
different dataset on purpose.

```bash
swebench report my-run                     # dataset taken from the run itself
swebench report my-run -d multimodal -i grommet__grommet-6282
```

## Submit

`swebench submit` has two destinations: the SWE-bench leaderboard (via
[`SWE-bench/experiments`](https://github.com/SWE-bench/experiments)) and HuggingFace's
eval-results system.

Every step takes the same run directory and reads what the last one recorded:

```bash
swebench submit package  logs/evaluation/my-run --trajs ./output
swebench submit publish  logs/evaluation/my-run -r <owner>/<name>
swebench submit register logs/evaluation/my-run
swebench submit verify   logs/evaluation/my-run
```

### `swebench submit package RUN_PATH`

Takes a run's log directory, or the model directory inside it. Writes two trees to
`<run>/submission/`, plus a `submission.json` that the later steps read:

```
submission-repo/     -> your own public GitHub repo
  all_preds.jsonl
  logs/<iid>/{patch.diff,report.json,test_output.txt.gz}
  trajs/<iid>.*
entry/               -> the PR to SWE-bench/experiments
  metadata.yaml  README.md  results/*.json
```

`logs/` matches the layout the S3 bucket has always used, so existing log consumers
work against a repo. Verdicts are **re-derived** from each `test_output.txt`, never
read from the run's own `report.json`.

The split comes from the dataset the run recorded. `--trajs` takes your agent's output
directory; traces are flattened to `trajs/<iid>.*`, and files not named after an
instance are skipped. Test output is gzipped, and anything still over 50MB is refused
with the instance named. Also: `-s`, `-o`, `--id`, `--model`, `-p/--predictions`.

### `swebench submit publish RUN_PATH`

Commits `submission-repo/` and pushes it. Name the destination: `-r/--repo
<owner>/<name>` creates it, `--remote <url>` pushes to one you made already. Writes the
URL into
`entry/metadata.yaml` as `assets.repo` / `assets.logs` / `assets.trajs` -- the field
that used to hold `s3://swe-bench-submissions/...`.

### `swebench submit register RUN_PATH`

Forks `SWE-bench/experiments`, adds `evaluation/<split>/<id>/`, and opens the PR with
the checklist in the body. It refuses while any `TODO` remains in `metadata.yaml` or
`README.md`, naming each one. Split and id come from `submission.json`. Also: `-s`,
`--id`, `--registry`, `--allow-todos`, `--dry-run`.

### `swebench submit verify RUN_PATH`

Clones the repo named in the entry's `assets.repo`, re-grades every instance from its
recorded test output, and reports any verdict that disagrees with `results.json`. No
Docker and no re-execution. Claiming an instance while shipping no log for it fails.

Takes a run directory, or an entry already committed to experiments. The split is
inferred from the path. `--logs` checks a local `logs/` tree instead of cloning. Anyone can run this, since artifacts are self-hosted.

### `swebench submit hf RUN_PATH`

Uploads a run's report to a HuggingFace bucket and writes a `.eval_results/*.yaml`
entry ([format](https://huggingface.co/docs/hub/eval-results)). The report and the
dataset come from the run, so only the bucket has to be named.

```bash
swebench submit hf my-run -b myuser/swebench-runs --public
swebench submit hf my-run -b myuser/runs --dry-run
```

The score is the report's `resolved_instances` / `total_instances`. Buckets are private
unless you pass `--public`, and a private bucket leaves the entry's URL unreadable to
anyone else. Needs the `submit` extra (`pip install swebench[submit]`).

## Images

Images are built from a task repo: each task carries its own Dockerfile, and its
`task.yaml` names the image the dataset will tell the harness to pull. Narrow
with `-i`, which can name a task in an unpublished split.

```bash
swebench images build ~/swe-bench-tasks -j 8
swebench images build ~/swe-bench-multimodal-tasks -i carbon-design-system__carbon-10188
swebench images build ~/swe-bench-tasks --dry-run

swebench images check ~/swe-bench-tasks    # which images are missing from the registry
swebench images push  ~/swe-bench-tasks    # publish them, under the names task.yaml declares
swebench images clean --run-id my-run      # remove leftover containers
```

`images check` is worth running before a long evaluation: it catches a stale or
partially-pushed image set in seconds rather than one instance at a time.
`images push --dry-run` prints the exact `docker push` commands and stops.

## Datasets

A task repo holds one directory per instance:

```
sweb.yaml                    the dataset this repo publishes, and its splits
tasks/<instance_id>/
    task.yaml                short metadata, including which split the task is in
    tests.json               the tests that decide whether a patch resolved it
    problem_statement.md     the issue text shown to a model
    hints.md                 discussion from the issue, absent when there is none
    gold.patch               the reference fix
    test.patch               the tests that grade it
    eval.sh                  the script the harness runs
    Dockerfile               the image it runs in
    assets/                  binary files a patch cannot carry
```

The tree is the source of truth. Nothing below reads HuggingFace to build the
dataset, so a new dataset can be developed entirely locally.

### `swebench dataset check TASK_REPO`

Check that a task repo is well formed: every task has its files, its metadata,
and a split registered in `sweb.yaml`. This runs automatically before building
or publishing, so a malformed tree is never published.

```bash
swebench dataset check ~/swe-bench-tasks
swebench dataset check ~/swe-bench-tasks --fix   # write back what the tree implies
```

`--fix` only writes what can be derived from the tree itself: the split list in
`sweb.yaml`, and image names that follow the naming convention. It never
invents data it cannot see.

### `swebench dataset build TASK_REPO`

Compile the repo into one parquet per split.

```bash
swebench dataset build ~/swe-bench-multilingual-tasks
swebench dataset build ~/swe-bench-tasks -o /tmp/parquets
```

### `swebench dataset diff TASK_REPO`

Show how the tree differs from the dataset it publishes, per column.

```bash
swebench dataset diff ~/swe-bench-multilingual-tasks
```

### `swebench dataset push TASK_REPO`

Overwrite the HuggingFace dataset named in `sweb.yaml`.

```bash
swebench dataset push ~/swe-bench-tasks --dry-run
swebench dataset push ~/swe-bench-tasks
```

A task whose split is not published, `deprecated` for example, stays in the tree
and can still be built by id, but never reaches the dataset.

### `swebench dataset collect REPOS...`

Scrape pull requests from GitHub into candidate task instances.

```bash
swebench dataset collect scikit-learn/scikit-learn
swebench dataset collect psf/requests --max-pulls 200 --cutoff-date 20230101
```

Versioning candidate instances is no longer part of this CLI. That tooling lives with
the task data, at [swe-bench-tasks/src/versioning](https://github.com/SWE-bench/swe-bench-tasks/tree/main/src/versioning).

## Older invocations

Every module is still runnable directly, with the same arguments as before:

```bash
python -m swebench.harness.run_evaluation --dataset_name ... --predictions_path ...
python -m swebench.image_builder.prepare_images --dataset_name ...
```

`swebench infer` covers agent-based inference via mini-SWE-agent. The older
completion-based utilities have no `swebench` subcommand and are run directly:

```bash
python -m swebench.inference.run_api --help
```
