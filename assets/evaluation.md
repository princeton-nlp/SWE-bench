# Evaluating with SWE-bench
John Yang &bull; November 6, 2023

In this tutorial, we will explain how to evaluate models and methods using SWE-bench.

## 🤖 Creating Predictions
For each task instance of the SWE-bench dataset, given an issue (`problem_statement`) + codebase (`repo` + `base_commit`), your model should attempt to write a diff patch prediction. For full details on the SWE-bench task, please refer to Section 2 of the main paper.

Each prediction must be formatted as follows:
```json
{
    "instance_id": "<Unique task instance ID>",
    "model_patch": "<.patch file content string>",
    "model_name_or_path": "<Model name here (i.e. SWE-Llama-13b)>",
}
```

Store multiple predictions in a `.json` file formatted as `[<prediction 1>, <prediction 2>,... <prediction n>]`. It is not necessary to generate predictions for every task instance.

If you'd like examples, the [swe-bench/experiments](https://github.com/swe-bench/experiments) GitHub repository contains many examples of well formed patches.

## 🔄 Running Evaluation
Evaluate model predictions on SWE-bench Lite using the evaluation harness with the following command:
```bash
python -m swebench.harness.run_evaluation \
    --dataset_name princeton-nlp/SWE-bench_Lite \
    --predictions_path <path_to_predictions> \
    --max_workers <num_workers> \
    --run_id <run_id>
    # use --predictions_path 'gold' to verify the gold patches
    # use --run_id to name the evaluation run
```
