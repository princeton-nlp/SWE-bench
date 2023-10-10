import argparse, json, logging, os, shutil

from constants import (
    KEY_INSTANCE_ID,
    KEY_MODEL,
    KEY_PREDICTION,
)
from engine_evaluation import main as eval_engine
from multiprocessing import Pool
from utils import get_instances

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("run_evaluation")


def validate_predictions(predictions_path, tasks_ids):
    # Check that predictions file exists
    if not any([predictions_path.endswith(x) for x in [".json", ".jsonl"]]):
        raise ValueError("Predictions path must be .json or .jsonl file")
    predictions = get_instances(predictions_path)
    not_in_tasks = []
    # Check that predictions are correctly formatted
    for pred in predictions:
        if any([x not in pred for x in [KEY_INSTANCE_ID, KEY_MODEL, KEY_PREDICTION]]):
            raise ValueError("Every prediction must have instance_id, model, and patch fields")
        if pred[KEY_INSTANCE_ID] not in tasks_ids:
            not_in_tasks.append(pred[KEY_INSTANCE_ID])
    # Check that instance IDs specified by predictions exist
    if len(not_in_tasks) > 0:
        logger.warning(
            "Predictions for the following instance_ids were not "
            + "found in the tasks file and will not be considered: "
            + ", ".join(not_in_tasks)
        )


def main(
    predictions_path: str,
    swe_bench_tasks: str,
    log_dir: str,
    testbed: str,
    skip_existing: bool,
    timeout: int,
    verbose: bool
):
    """
    Runs evaluation on predictions for each model/repo/version combination.

    Args:
        predictions_path (str): Path to the predictions file.
        swe_bench_tasks (str): Path to the SWE-bench tasks file.
        log_dir (str): Path to the directory where logs will be saved.
        testbed (str): Path to the directory where testbeds will be saved.
        skip_existing (bool): Whether to skip evaluations for predictions that already have logs.
        timeout (int): Timeout for each evaluation.
        verbose (bool): Whether to print verbose output.

    Raises:
        ValueError: If log_dir is not a directory, testbed is not a directory, or swe_bench_tasks does not exist.
    """
    # Validate arguments
    if not os.path.isdir(log_dir):
        raise ValueError("--log_dir must be a directory")
    if not os.path.isdir(testbed):
        raise ValueError("--testbed must be a directory")
    if not os.path.exists(swe_bench_tasks):
        raise ValueError("--swe_bench_tasks does not exist")
    tasks = json.load(open(swe_bench_tasks))
    tasks_map = {t[KEY_INSTANCE_ID]: t for t in tasks}
    validate_predictions(predictions_path, [t[KEY_INSTANCE_ID] for t in tasks])

    # Group predictions by model
    predictions = json.load(open(predictions_path))
    map_model_to_predictions = {}
    for p in predictions:
        model = p[KEY_MODEL]
        if model not in map_model_to_predictions:
            map_model_to_predictions[model] = []
        map_model_to_predictions[model].append(p)
    logger.info(f"Found {len(predictions)} predictions across {len(map_model_to_predictions)} model(s) in predictions file")
    
    # For each model, split predictions by repo + save to folder
    eval_args = []
    temp_dirs = []
    for model, predictions in map_model_to_predictions.items():
        # Group predictions by repository, version
        map_repo_version_to_predictions = {}
        for p in predictions:
            repo = p[KEY_INSTANCE_ID].rsplit("-", 1)[0]
            if repo not in map_repo_version_to_predictions:
                map_repo_version_to_predictions[repo] = {}
            t = tasks_map[p[KEY_INSTANCE_ID]]
            p.update(t)
            version = t["version"]
            if version not in map_repo_version_to_predictions[repo]:
                map_repo_version_to_predictions[repo][version] = []
            map_repo_version_to_predictions[repo][version].append(p)
        
        # For each model/repo/version, create testbed folder and save predictions
        for repo in map_repo_version_to_predictions:
            for version in map_repo_version_to_predictions[repo]:
                # Create testbed folder + file for model/repo/version specific predictions
                testbed_model_repo_version_dir = os.path.join(testbed, model, repo, version)
                os.makedirs(testbed_model_repo_version_dir, exist_ok=True)
                file_name = f"{model}_{repo}_{version}_{predictions_path.split('/')[-1]}"
                file_path = os.path.join(testbed_model_repo_version_dir, file_name)
                with open(file_path, "w") as f:
                    args = argparse.Namespace()
                    args.log_dir = os.path.join(log_dir, model)
                    args.temp_dir = testbed_model_repo_version_dir
                    args.num_workers = 1
                    args.timeout = timeout
                    args.skip_existing = skip_existing
                    args.verbose = verbose

                    repo_version_predictions = map_repo_version_to_predictions[repo][version]
                    if skip_existing:
                        # Skip logs that already exist
                        predictions_filtered = []
                        for p in repo_version_predictions:
                            log_file = os.path.join(
                                args.log_dir,
                                f"{p[KEY_INSTANCE_ID]}.{p[KEY_MODEL]}.eval.log",
                            )
                            if not os.path.exists(log_file):
                                predictions_filtered.append(p)
                        if len(predictions_filtered) == 0:
                            logger.info(f"[{model}/{repo}/{version}] All predictions already exist, skipping")
                            continue
                        else:
                            logger.info(
                                f"[{model}/{repo}/{version}] # of predictions to evaluate: {len(predictions_filtered)} " + 
                                f"({len(repo_version_predictions) - len(predictions_filtered)} already evaluated)"
                            )
                            repo_version_predictions = predictions_filtered
                    else:
                        logger.info(f"[{model}/{repo}/{version}] # of predictions to evaluate: {len(repo_version_predictions)}")

                    json.dump(repo_version_predictions, f, indent=4)
                    args.predictions_path = file_path

                    eval_args.append(args)
                temp_dirs.append(testbed_model_repo_version_dir)
    
    # Run evaluation on each model/repo
    pool = Pool(processes=len(eval_args))
    pool.map(eval_engine, eval_args)
    pool.close()
    pool.join()

    # Clean up
    for temp_dir in temp_dirs:
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions_path", type=str, help="Path to predictions file (must be .json)", required=True)
    parser.add_argument("--log_dir", type=str, help="Path to log directory", required=True)
    parser.add_argument("--swe_bench_tasks", type=str, help="Path to SWE-bench task instances file", required=True)
    parser.add_argument("--testbed", type=str, help="Path to testbed directory", required=True)
    parser.add_argument("--skip_existing", action="store_true", help="(Optional) Skip existing logs")
    parser.add_argument("--timeout", type=int, help="(Optional) Timeout in seconds (default: 900)", default=900)
    parser.add_argument("--verbose", action="store_true", help="(Optional) Verbose mode")
    args = parser.parse_args()
    logger.propagate = args.verbose
    main(**vars(args))
