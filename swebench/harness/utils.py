import json
import traceback

from argparse import ArgumentTypeError
from concurrent.futures import ThreadPoolExecutor, as_completed
from datasets import Dataset, load_dataset, load_from_disk
from dotenv import load_dotenv
from pathlib import Path
from tqdm import tqdm
from typing import cast
from swebench.harness.constants import (
    END_TEST_OUTPUT,
    TEST_EXIT_CODE,
    TEST_EXIT_CODE_VAR,
)
from swebench.types import SWEbenchInstance, TestSpec


load_dotenv()


class EvaluationError(Exception):
    def __init__(self, instance_id, message, logger):
        super().__init__(message)
        self.super_str = super().__str__()
        self.instance_id = instance_id
        self.log_path = logger.log_file
        self.logger = logger

    def __str__(self):
        return (
            f"Error in evaluation for {self.instance_id}: {self.super_str}\n"
            f"Check ({self.log_path}) for more information."
        )


def get_predictions_from_file(
    predictions_path: str,
    dataset_name: str,
    split: str,
    task_repo: str | None = None,
    instance_ids: list | None = None,
):
    if predictions_path in {"gold", "no-patch"}:
        print(f"Using {predictions_path} predictions - ignoring predictions_path")
        # the gold patch has to come from wherever the rest of the instance came from,
        # or a run against a task repo silently grades the dataset's patch instead and
        # never notices the two disagreeing
        if task_repo:
            from swebench.task.repo import load_task_repo

            dataset = load_task_repo(task_repo, instance_ids)
            if not instance_ids:
                dataset = [d for d in dataset if d.get("split") == split]
        else:
            dataset = load_swebench_dataset(dataset_name, split, instance_ids)
        return [
            {
                "instance_id": datum["instance_id"],
                "model_patch": (
                    datum["patch"]
                    if predictions_path == "gold"
                    else "__SWEBENCH_NO_PATCH__"
                ),
                "model_name_or_path": (
                    "gold" if predictions_path == "gold" else "no_patch"
                ),
                "skip_patch": predictions_path == "no-patch",
                "reference_patch": predictions_path == "gold",
            }
            for datum in dataset
        ]
    if predictions_path.endswith(".json"):
        with open(predictions_path, "r") as f:
            predictions = json.load(f)
            if isinstance(predictions, dict):
                predictions = list(
                    predictions.values()
                )  # compatible with SWE-agent predictions
            if not isinstance(predictions, list):
                raise ValueError(
                    "Predictions must be a list[prediction] or a dictionary[instance_id: prediction]"
                )
    elif predictions_path.endswith(".jsonl"):
        with open(predictions_path, "r") as f:
            predictions = [json.loads(line) for line in f]
    else:
        raise ValueError("Predictions path must be .json or .jsonl")

    # Validate that each prediction has an instance_id
    for pred in predictions:
        if not isinstance(pred, dict):
            raise ValueError(f"Each prediction must be a dictionary, got {type(pred)}")
        if "instance_id" not in pred:
            raise ValueError(f"Each prediction must contain '{'instance_id'}'")

    return predictions


def run_threadpool(func, payloads, max_workers):
    if max_workers <= 0:
        return run_sequential(func, payloads)
    succeeded, failed = [], []
    with tqdm(total=len(payloads), smoothing=0) as pbar:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Create a future for running each instance
            futures = {executor.submit(func, *payload): payload for payload in payloads}
            # Wait for each future to complete
            for future in as_completed(futures):
                try:
                    # Check if instance ran successfully
                    future.result()
                    succeeded.append(futures[future])
                except Exception as e:
                    print(f"{type(e)}: {e}")
                    traceback.print_exc()
                    failed.append(futures[future])
                # Update progress bar
                pbar.update(1)
                pbar.set_description(
                    f"{len(succeeded)} ran successfully, {len(failed)} failed"
                )
    return succeeded, failed


def run_sequential(func, args_list):
    """
    Run a function with a list of arguments sequentially
    """
    succeeded, failed = [], []
    pbar = tqdm(total=len(args_list), smoothing=0)
    for args in args_list:
        try:
            func(*args)
            succeeded.append(args)
        except Exception:
            traceback.print_exc()
            failed.append(args)
        pbar.update(1)
        pbar.set_description(f"{len(succeeded)} ran successfully, {len(failed)} failed")
    pbar.close()
    return succeeded, failed


def load_swebench_dataset(
    name="SWE-bench/SWE-bench", split="test", instance_ids=None
) -> list[SWEbenchInstance]:
    """
    Load SWE-bench dataset from Hugging Face Datasets or local .json/.jsonl file
    """
    # check that all instance IDs are in the dataset
    if instance_ids:
        instance_ids = set(instance_ids)
    # Load from local file
    if name.endswith(".json"):
        dataset = json.loads(Path(name).read_text())
    elif name.endswith(".jsonl"):
        dataset = [json.loads(line) for line in Path(name).read_text().splitlines()]
    elif name.endswith(".parquet"):
        dataset = cast(Dataset, load_dataset("parquet", data_files=name, split="train"))
    else:
        # Load from Hugging Face Datasets
        if name.lower() in {"swe-bench", "swebench", "swe_bench"}:
            name = "SWE-bench/SWE-bench"
        elif name.lower() in {
            "swe-bench-lite",
            "swebench-lite",
            "swe_bench_lite",
            "swe-bench_lite",
            "lite",
        }:
            name = "SWE-bench/SWE-bench_Lite"
        parquet_path = Path(name) / f"{split}.parquet"
        if parquet_path.exists():
            dataset = cast(
                Dataset,
                load_dataset("parquet", data_files=str(parquet_path), split="train"),
            )
        elif (Path(name) / split / "dataset_info.json").exists():
            dataset = cast(Dataset, load_from_disk(Path(name) / split))
        else:
            dataset = cast(Dataset, load_dataset(name, split=split))
    dataset_ids = {instance["instance_id"] for instance in dataset}
    if instance_ids:
        if instance_ids - dataset_ids:
            raise ValueError(
                (
                    "Some instance IDs not found in dataset!"
                    f"\nMissing IDs:\n{' '.join(instance_ids - dataset_ids)}"
                )
            )
        dataset = [
            instance for instance in dataset if instance["instance_id"] in instance_ids
        ]
    return [cast(SWEbenchInstance, instance) for instance in dataset]


def str2bool(v):
    """
    Minor helper function to convert string to boolean
    """
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise ArgumentTypeError("Boolean value expected.")


def optional_str(value: str) -> str | None:
    """
    Convert special string values to None, otherwise return the string as-is.
    """
    if value.lower() in ("none", "null", ""):
        return None
    return value


def parse_eval_script(eval_script: str) -> list[str]:
    """Parse an eval.sh script into a command list (strip shebang + set flags)."""
    return [
        line
        for line in eval_script.strip().split("\n")
        if line not in ("#!/bin/bash", "set -uxo pipefail")
    ]


def record_test_exit_code(eval_script_list: list[str]) -> list[str]:
    """Make the eval script record the test command's own exit status.

    Eval scripts end with a `git checkout` that resets the test files, and run
    under `set -uxo pipefail` without `-e`, so the script's exit status is the
    reset's, not the tests'. Capturing `$?` immediately after the test command
    and echoing it after the end marker keeps the value out of the parsed region.
    """
    for i, line in enumerate(eval_script_list):
        if END_TEST_OUTPUT in line:
            return [
                *eval_script_list[:i],
                f"{TEST_EXIT_CODE_VAR}=$?",
                line,
                f'echo "{TEST_EXIT_CODE}: ${TEST_EXIT_CODE_VAR}"',
                *eval_script_list[i + 1 :],
            ]
    # No end marker (unrecognized script shape): leave it untouched, and grading
    # falls back to the pre-existing behavior of trusting the log alone.
    return eval_script_list


def _parse_image_assets(raw) -> dict:
    """image_assets ships as a JSON string in the HF datasets, dict when local."""
    if not raw:
        return {}
    return json.loads(raw) if isinstance(raw, str) else raw


def make_test_spec(instance: dict) -> TestSpec:
    """
    Build a TestSpec from a dataset instance.

    The instance dict must contain: instance_id, image, repo, version,
    FAIL_TO_PASS, PASS_TO_PASS, log_parser, eval_type, eval_script.
    """
    f2p = instance["FAIL_TO_PASS"]
    p2p = instance["PASS_TO_PASS"]
    return TestSpec(
        instance_id=instance["instance_id"],
        image=instance["image"],
        eval_script_list=record_test_exit_code(
            parse_eval_script(instance["eval_script"])
        ),
        repo=instance["repo"],
        version=instance["version"],
        FAIL_TO_PASS=json.loads(f2p) if isinstance(f2p, str) else f2p,
        PASS_TO_PASS=json.loads(p2p) if isinstance(p2p, str) else p2p,
        log_parser=instance["log_parser"],
        eval_type=instance["eval_type"],
        image_assets=_parse_image_assets(instance.get("image_assets")),
    )
