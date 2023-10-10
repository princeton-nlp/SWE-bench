"""Provided a source (raw) directory and the final (eval) directory, create a training split by removing all instances that are in the final directory from the source directory.
"""

import json
import logging
import random
from argparse import ArgumentParser
from pathlib import Path
from datasets import Dataset, DatasetDict, load_dataset
from tqdm.auto import tqdm

try:
    from create_instance import PROMPT_FUNCTIONS, add_text_inputs
    from tokenize_dataset import TOKENIZER_FUNCS
    from utils import string_to_bool
else:
    from .create_instance import PROMPT_FUNCTIONS, add_text_inputs
    from .tokenize_dataset import TOKENIZER_FUNCS
    from .utils import string_to_bool

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_jsonl_file(filename):
    if type(filename) == str:
        filename = Path(filename)
    if filename.name.endswith(".jsonl") or filename.name.endswith(".jsonl.all"):
        with open(filename) as f:
            return [json.loads(line) for line in f]
    elif filename.name.endswith(".json"):
        with open(filename) as f:
            return json.load(f)
    else:
        raise ValueError(f"Unknown file type {filename}")


def instances_generator(files):
    all_data = list()
    for file in tqdm(files, desc="Loading instance files"):
        all_data.extend(load_jsonl_file(file))
    return all_data


def get_training_and_eval_instances(raw_files, test_dataset):
    logger.info("Loading instances")
    raw_instances = list(instances_generator(raw_files))
    final_instances = list(test_dataset["test"])
    eval_repos = {x["repo"] for x in final_instances}
    train_instances = [x for x in raw_instances if x["repo"] not in eval_repos]
    train_instances = list(sorted(train_instances, key=lambda x: x["instance_id"]))
    eval_instances = list(sorted(final_instances, key=lambda x: x["instance_id"]))
    logger.info(f"Found {len(train_instances)} training ids")
    logger.info(f"Found {len(eval_instances)} eval ids")
    return train_instances, eval_instances


def extract_fields(instance):
    instance_id = instance["instance_id"]
    if instance["text_inputs"] is None or instance["patch"] is None:
        print(f"No text for {instance_id}")
        return None
    text_inputs = instance["text_inputs"].strip() + "\n\n"
    if text_inputs is None or instance["patch"] is None:
        print(f"No inputs for {instance_id}")
        return None
    patch = "\n".join([f"<patch>", instance["patch"], "</patch>"])
    return {**instance, "text": text_inputs, "patch": patch}


def main(
    raw_dir,
    test_dataset,
    output_dir,
    validation_ratio,
    github_token,
    retrieval_dir,
    prompt_style,
    file_source,
    k,
    python_only_patch,
    skip_train,
    max_context_len,
    tokenizer_name,
):
    if max_context_len is not None:
        assert tokenizer_name is not None
    if not Path(output_dir).exists():
        Path(output_dir).mkdir(parents=True)
    output_file = f"swe_prs_clean.{prompt_style}__po-{int(python_only_patch)}__st-{int(skip_train)}__fs-{file_source}"
    if k is not None:
        output_file += f"__k-{k}"
    if max_context_len is not None:
        output_file += f"__mcc-{max_context_len}-{tokenizer_name}"
    output_file = Path(output_dir, output_file)
    if output_file.exists():
        logger.info(f"Found {output_file.absolute().as_posix()}. Skipping")
        return
    test_dataset = load_dataset(test_dataset)
    training_instances, eval_instances = get_training_and_eval_instances(
        list(Path(raw_dir).glob("*.all")) if not skip_train else [],
        test_dataset,
    )
    if skip_train:
        training_instances = list()
    training_instances = {x["instance_id"]: x for x in training_instances}
    eval_instances = {x["instance_id"]: x for x in eval_instances[:20]}
    add_text_inputs(
        training_instances,
        retrieval_dir,
        k,
        github_token,
        prompt_style,
        file_source,
        python_only=python_only_patch,
        max_context_len=max_context_len,
        tokenizer_name=tokenizer_name,
    )
    add_text_inputs(
        eval_instances,
        retrieval_dir,
        k,
        github_token,
        prompt_style,
        file_source,
        python_only=python_only_patch,
        max_context_len=max_context_len,
        tokenizer_name=tokenizer_name,
    )
    breakpoint()
    columns = [
        "instance_id",
        "repo",
        "base_commit",
        "problem_statement",
        "hints_text",
        "created_at",
        "patch",
        "test_patch",
        "version",
        "FAIL_TO_PASS",
        "PASS_TO_PASS",
        "environment_setup_commit",
        "text_inputs",
    ]
    data = {key: list() for key in columns}
    test_data = {key: list() for key in columns}
    for instance_id, instance in tqdm(
        training_instances.items(),
        total=len(training_instances),
        desc="Creating training split",
    ):
        datum = extract_fields(instance)
        if datum is None:
            continue
        for key in columns:
            data[key].append(instance[key] if key in instance else '')
    for instance_id, instance in tqdm(
        eval_instances.items(), total=len(eval_instances), desc="Creating test split"
    ):
        datum = extract_fields(instance)
        if datum is None:
            continue
        for key in columns:
            test_data[key].append(instance[key] if key in instance else '')
    logger.info(f"Found {len(data['instance_id'])} training ids")
    logger.info(f"Found {len(test_data['instance_id'])} eval ids")
    trainval_dataset = Dataset.from_dict(data)
    testval_dataset = Dataset.from_dict(test_data)
    random.seed(42)
    validation_ids = random.sample(
        range(len(trainval_dataset)),
        int(round(validation_ratio * len(trainval_dataset))),
    )
    validation_2_ids = random.sample(
        range(len(testval_dataset)),
        int(round(0.1 * len(testval_dataset))),
    )
    train_ids = list(set(range(len(trainval_dataset))) - set(validation_ids))
    test_ids = list(set(range(len(testval_dataset))) - set(validation_2_ids))
    train_dataset = trainval_dataset.select(train_ids)
    validation_dataset = trainval_dataset.select(validation_ids)
    test_dataset = testval_dataset.select(test_ids)
    dataset = DatasetDict(
        {
            "train": train_dataset,
            "validation": validation_dataset,
            "test": test_dataset,
        }
    )
    logger.info(
        f"Saving {len(dataset['train'])} training instances and {len(dataset['validation'])} validation instances to {output_file} and {len(dataset['test'])} test instances to {output_file}"
    )
    dataset.save_to_disk(output_file)
    logger.info(f"Finsihed saving to {output_file}")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--raw_dir", type=str, required=False, help="Raw task instance outputs from collect.build_dataset.py. If you want to skip the training set, don't provide this.")
    parser.add_argument("--test_dataset", type=str, default="princeton-nlp/SWE-bench", help="Dataset to use for test set from HuggingFace Datasets.")
    parser.add_argument("--output_dir", type=str, required=True, help="Path to the output directory.")
    parser.add_argument("--validation_ratio", type=float, default=0.01, help="Ratio of training instances to use for validation.")
    parser.add_argument("--github_token", type=str, help="GitHub token.")
    parser.add_argument(
        "--skip_train", type=string_to_bool, nargs="?", const=True, default=False, help="Whether to skip the training set."
    )
    parser.add_argument(
        "--retrieval_dir",
        type=str,
        help="Path to the directory where the retrieval results are stored.",
    )
    parser.add_argument(
        "--prompt_style",
        type=str,
        default="style-3",
        choices=PROMPT_FUNCTIONS.keys(),
        help="Prompt style to use. See create_instance.PROMPT_FUNCTIONS for details.",
    )
    parser.add_argument(
        "--file_source",
        type=str,
        default="oracle",
        choices=["oracle", "bm25", "all", "oracle-edits-only"],
        help="Where to get the files from.",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=None,
        help="Maximum number of files to use for retrieval.",
    )
    parser.add_argument(
        "--python_only_patch",
        type=string_to_bool,
        default=False,
        required=True,
        const=True,
        nargs="?",
        help="Path to the output file.",
    )
    parser.add_argument("--max_context_len", type=int, default=None)
    parser.add_argument(
        "--tokenizer_name",
        type=str,
        default=None,
        choices=TOKENIZER_FUNCS.keys(),
    )
    main(**vars(parser.parse_args()))
