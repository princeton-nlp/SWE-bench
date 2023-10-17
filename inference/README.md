# SWE-bench Inference
In this package, we provide various tools to get started on SWE-bench inference.
In particular, we provide the following important scripts and sub-packages:

- `make_datasets`, this sub-package contains scripts to generate new datasets for SWE-bench inference with your own prompts and issues.
- `run_api.py`, this script is used to generate API model generations for a given dataset.
- `run_live.py`, this script is used to generate model generations for new issues on GitHub in real time.

## `make_datasets`
For more information on how to use this sub-package, please refer to the [README](./make_datasets/README.md) in the sub-package.

## Run API inference on test datasets

This python script is designed to run inference on a dataset using either the OpenAI or Anthropic API, depending on the model specified. It sorts instances by length and continually writes the outputs to a specified file, so that the script can be stopped and restarted without losing progress.

For instance, to run this script on SWE-bench with the ``Oracle`` context and Anthropic's Claude 2 model, you can run the following command:
```bash
export ANTHROPIC_API_KEY=<your key>
python run_api.py --dataset_name_or_path princeton-nlp/SWE-bench_oracle_llama --model_name_or_path claude-2 --output_dir ./outputs
```

You can also specify further options:

- `--split`: To specify the dataset split to use (default is "test").
- `--shard_id` and `--num_shards`: To process only a shard of the data.
- `--model_args`: A string containing comma-separated key=value pairs for arguments to pass to the model. (e.g. `--model_args="temperature=0.2,top_p=0.95"`)
- `--max_cost`: The maximum cost to spend on inference (for OpenAI API only).


## Run live inference on open GitHub issues

Follow instructions [here](https://github.com/castorini/pyserini/blob/master/docs/installation.md) to install [Pyserini](https://github.com/castorini/pyserini), to perform BM25 retrieval.

Then run `run_live.py` to try solving a new issue. For example, you can try solving [this issue](https://github.com/huggingface/transformers/issues/26706 ) by running the following command:

```bash
export OPENAI_API_KEY=<your key>
python run_live.py --model_name gpt-3.5-turbo-16k \
    --issue_url https://github.com/huggingface/transformers/issues/26706 
```
