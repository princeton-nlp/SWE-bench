# Infer Open-Source Models

## Prerequisite

We leverage libraries such as [vllm](https://github.com/vllm-project/vllm) and [lmdeploy](https://github.com/InternLM/lmdeploy), with the OpenAI interface, for model deployment and inference.

> lmdeploy could be [faster](https://github.com/InternLM/lmdeploy?tab=readme-ov-file#performance) than vllm.

The version of the OpenAI package previously used in SWE-bench (<1.0.0) is outdated and lacks support for explicit client instantiation, which is crucial for our deployment process. To resolve this, please upgrade to a compatible version:

```shell
pip install openai==1.14.2
```

For detailed model deployment instructions, refer to the documentation provided within the respective libraries.

## Inference Process

### Create dataset

To prepare the dataset, follow the step-by-step guide provided in the [swe-bench make_datasets documentation](./make_datasets/README.md)

For brevity, run the following:
```shell
export GITHUB_TOKEN=YOUR_GITHUB_TOKEN
python create_text_dataset.py --dataset_name_or_path princeton-nlp/SWE-bench_lite --output_dir PATH_TO_DATASET --prompt_style style-3 --file_source oracle --tokenizer_name MODEL_NAME --splits test
```

This command creates a dataset in the specified `PATH_TO_DATASET/princeton-nlp/{dataset_name_or_path}__{prompt_style}__fs-{file_source}__tok-{tokenizer_name}` directory.

Please note that the tokenizer primarily serves to limit the maximum context length. The output dataset folder will always have a tokenizer suffix. However, actual enforcement of the length constraint won't take effect if `max_context_len` is not specified. Given that creating dataset is a time-consuming process, you can reuse previously created datasets with any tokenizer and length constraint will be conducted automatically at the inference phase.

### Run Inference

Please follow the instructions in swe-bench [inference](./README.md) to perform model inferece.

To proceed, execute the following:
```shell
export DEPLOYMENT_API_KEY=YOUR_DEPLOYMENT_API_KEY
export DEPLOYMENT_URL=YOUR_DEPLOYMENT_URL
python run_api.py --dataset_name_or_path PATH_TO_DATASET --model_name_or_path MODEL_NAME --output_dir PATH_TO_OUTPUTS
```

Ensure you provide the `DEPLOYMENT_API_KEY`` if it was specified during deployment; otherwise, replace it with just a placeholder.

This command generates an output directory structured as `PATH_TO_OUTPUTS/{MODEL_NAME}__{PATH_TO_DATASET.split('/')[-1]}__{split}`.


