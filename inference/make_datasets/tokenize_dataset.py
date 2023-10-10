"""Provided a source (raw) directory and the final (eval) directory, create a training split by removing all instances that are in the final directory from the source directory.
"""

import logging
from argparse import ArgumentParser
from pathlib import Path

import tiktoken
from datasets import disable_caching, load_from_disk
from tqdm.auto import tqdm
from transformers import LlamaTokenizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
logger.warning("Disabling caching")
disable_caching()


def cl100k(text, tokenizer):
    return tokenizer.encode(text, disallowed_special=())


def llama(text, tokenizer):
    return tokenizer(text, add_special_tokens=False, return_attention_mask=False)[
        "input_ids"
    ]


TOKENIZER_FUNCS = {
    "cl100k": (tiktoken.get_encoding("cl100k_base"), cl100k),
    "llama": (LlamaTokenizer.from_pretrained("togethercomputer/LLaMA-2-7B-32K"), llama),
}


def extract_fields(instance, tokenizer_name, tokenizer, tokenizer_func, eos_token):
    instance_id = instance["instance_id"]
    if instance["text"] is None or instance["patch"] is None:
        print(f"No text for {instance_id}")
        return {"input_ids": [], "labels": [], "text": "", "patch": ""}
    text_inputs = instance["text"].strip() + "\n"
    if text_inputs is None or instance["patch"] is None:
        print(f"No inputs for {instance_id}")
        return None
    patch = instance["patch"].strip()
    if len(eos_token) > 0:
        patch += f"\n{eos_token}"
    input_ids = tokenizer_func(text_inputs, tokenizer)
    if tokenizer_name in {"llama"}:
        label_ids = tokenizer_func(
            "\n" + patch, tokenizer
        )  # add newline to tokenize patch
        idx = label_ids.index(13)
        assert (
            idx <= 2
        ), "Expected newline token id (13) to be one of the first three tokens"
        label_ids = label_ids[idx + 1 :]  # remove newline tokens
    else:
        label_ids = tokenizer_func(patch, tokenizer)
    inputs = input_ids + label_ids[:-1]
    cond_len = len(input_ids) - 1
    labels = [-100] * cond_len + label_ids
    assert len(inputs) == len(labels)
    return {**instance, "input_ids": inputs, "labels": labels, "text": text_inputs, "patch": patch}


def extract_test_fields(instance, tokenizer_name, tokenizer, tokenizer_func, eos_token):
    instance_id = instance["instance_id"]
    if instance["text"] is None or instance["patch"] is None:
        print(f"No text for {instance_id}")
        return None
    text_inputs = instance["text"].strip() + "\n"
    if text_inputs is None or instance["patch"] is None:
        print(f"No inputs for {instance_id}")
        return None
    patch = instance["patch"].strip()
    if len(eos_token) > 0:
        patch += f"\n{eos_token}"
    input_ids = tokenizer_func(text_inputs, tokenizer)
    label_ids = tokenizer_func(patch, tokenizer)
    inputs = input_ids
    labels = label_ids
    return {**instance, "input_ids": inputs, "labels": labels, "text": text_inputs, "patch": patch}


def add_columns_from_dict(dataset, dict_columns):
    """dict_columns is a list of dicts with keys that are columns in dataset"""
    for column in dict_columns[0].keys():
        values = [d[column] for d in dict_columns]
        if column in dataset.column_names:
            dataset = dataset.remove_columns(column)
        dataset = dataset.add_column(column, values)
    return dataset


def main(
    dataset_path,
    output_dir,
    max_length,
    tokenizer_name,
    num_proc,
    no_map,
):
    if not Path(output_dir).exists():
        Path(output_dir).mkdir(parents=True)

    if tokenizer_name is not None:
        tokenizer, tokenizer_func = TOKENIZER_FUNCS[tokenizer_name]
        eos_token = getattr(tokenizer, "eos_token", "")

    dataset = load_from_disk(dataset_path)
    dataset = dataset.filter(lambda x: len(x["text"]) <= 5_000_000)
    for split in ["train", "validation"]:
        if split not in dataset:
            logger.warning(f"Split {split} not in dataset. Skipping")
            continue
        if not no_map:
            dataset[split] = dataset[split].map(
                lambda instance: extract_fields(
                    instance,
                    tokenizer_name,
                    tokenizer,
                    tokenizer_func,
                    eos_token,
                ),
                num_proc=num_proc,
                batched=False,
                desc=f"Tokenizing {split}",
            )
        elif len(dataset[split]) > 0:
            new_values = list(
                map(
                    lambda x: extract_fields(
                        x, tokenizer_name, tokenizer, tokenizer_func, eos_token
                    ),
                    tqdm(
                        dataset[split],
                        total=len(dataset[split]),
                        desc=f"Tokenizing {split}",
                    ),
                )
            )
            dataset[split] = add_columns_from_dict(dataset[split], new_values)
    for split in ["minitest", "test"]:
        if split not in dataset:
            logger.warning(f"Split {split} not in dataset. Skipping")
            continue
        if not no_map:
            dataset[split] = dataset[split].map(
                lambda instance: extract_test_fields(
                    instance,
                    tokenizer_name,
                    tokenizer,
                    tokenizer_func,
                    eos_token,
                ),
                num_proc=num_proc,
                batched=False,
                desc=f"Tokenizing {split}",
            )
        elif len(dataset[split]) > 0:
            new_values = list(
                map(
                    lambda x: extract_test_fields(
                        x, tokenizer_name, tokenizer, tokenizer_func, eos_token
                    ),
                    tqdm(
                        dataset[split],
                        total=len(dataset[split]),
                        desc=f"Tokenizing {split}",
                    ),
                )
            )
            dataset[split] = add_columns_from_dict(dataset[split], new_values)
    if max_length is not None:
        for split in ["train", "validation"]:
            if split not in dataset:
                logger.warning(f"Split {split} not in dataset. Skipping")
                continue
        logger.warning(f"Filtering {split} to max length {max_length}")
        dataset[split] = dataset[split].filter(
            lambda instance: len(instance["input_ids"]) <= max_length,
            num_proc=num_proc,
            batched=False,
        )
    output_file = Path(dataset_path).name + f"__tok-{tokenizer_name}"
    if max_length is not None:
        output_file += f"__max-{max_length}"
    output_file = Path(output_dir) / output_file
    logger.warning(f"Saving to {output_file}")
    dataset.save_to_disk(output_file)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--dataset_path", type=str, required=True)
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--max_length", type=int, default=None)
    parser.add_argument(
        "--tokenizer_name", type=str, required=True, choices=TOKENIZER_FUNCS.keys()
    )
    parser.add_argument("--num_proc", type=int, default=5)
    parser.add_argument("--no_map", type=bool, default=False)
    main(**vars(parser.parse_args()))
