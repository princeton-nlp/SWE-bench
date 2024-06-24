# import json
# import resource
# import traceback
# from argparse import ArgumentParser
# from concurrent.futures import ThreadPoolExecutor, as_completed
# from pathlib import Path

# import docker
# from tqdm import tqdm

# from swebench.harness.utils import str2bool
# from swebench.harness.grading import get_model_report
# from swebench.harness.docker_utils import (
#     close_logger,
#     setup_logger,
#     get_session_id,
#     cleanup_image,
#     copy_to_container,
#     exec_run_with_timeout,
#     cleanup_container,
#     list_images,
#     build_container,
#     build_env_images,
#     INSTANCE_IMAGE_BUILD_DIR,
# )
# from swebench.harness.dataset import load, make_test_spec


# RUN_INSTANCE_LOG_DIR = Path("run_instance_logs")


# def get_dataset_from_preds(instance_ids, predictions, exclude_completed=True):


# def should_remove(image_name, cache, clean, prior_images):
#     """
#     Determine if an image should be removed based on cache level and clean flag.
#     """
#     existed_before = image_name in prior_images
#     if image_name.startswith("sweb.base"):
#         if cache in {"none"} and (clean or not existed_before):
#             return True
#     elif image_name.startswith("sweb.env"):
#         if cache in {"none", "base"} and (clean or not existed_before):
#             return True
#     elif image_name.startswith("sweb.eval"):
#         if cache in {"none", "base", "env"} and (clean or not existed_before):
#             return True
#     return False


# def clean_images(client, prior_images, cache, clean):
#     images = list_images(client)
#     removed = 0
#     print(f"Cleaning cached images...")
#     for image_name in images:
#         if should_remove(image_name, cache, clean, prior_images):
#             try:
#                 cleanup_image(client, image_name, True, "quiet")
#                 removed += 1
#             except Exception as e:
#                 print(f"Error removing image {image_name}: {e}")
#                 continue
#     print(f"Removed {removed} images.")


# def main(
#     instance_ids,
#     predictions_path,
#     max_workers,
#     force_rebuild,
#     cache,
#     clean,
#     open_file_limit,
#     session_id,
#     timeout,
# ):
#     if not session_id:
#         session_id = get_session_id(8)
#     else:
#         assert len(session_id) == 8, "Session ID must be 8 characters long."
#     resource.setrlimit(resource.RLIMIT_NOFILE, (open_file_limit, open_file_limit))
#     client = docker.from_env()
#     with open(predictions_path, "r") as f:
#         predictions = json.loads(f.read())
#     predictions = {pred["instance_id"]: pred for pred in predictions}
#     dataset = get_dataset_from_preds(instance_ids, predictions)
#     full_dataset = get_dataset_from_preds(instance_ids, predictions, exclude_completed=False)
#     existing_images = list_images(client)
#     print(f"Running {len(dataset)} unevaluated instances...")
#     if not dataset:
#         print("No instances to run.")
#     else:
#         build_env_images(dataset, client, force_rebuild, max_workers)
#         run_instances(predictions, dataset, cache, clean, force_rebuild, max_workers, session_id, timeout)
#     clean_images(client, existing_images, cache, clean)
#     make_run_report(predictions, full_dataset, client, session_id)


# if __name__ == "__main__":
#     parser = ArgumentParser()
#     parser.add_argument("--instance_ids", nargs="+", type=str, help="Instance IDs to run")
#     parser.add_argument("--predictions_path", type=str, help="Path to predictions file")
#     parser.add_argument("--max_workers", type=int, default=4, help="Maximum number of workers")
#     parser.add_argument("--open_file_limit", type=int, default=4096, help="Open file limit")
#     parser.add_argument("--timeout", type=int, default=1_800, help="Timeout for running tests for each instance")
#     parser.add_argument(
#         "--force_rebuild", type=str2bool, default=False, help="Force rebuild of images"
#     )
#     parser.add_argument(
#         "--cache",
#         type=str,
#         choices=["none", "base", "env", "instance"],
#         help="Cache level",
#         default="env",
#     )
#     # if clean is true then we remove all images that are above the cache level
#     # if clean is false, we only remove images above the cache level if they don't already exist
#     parser.add_argument(
#         "--clean", type=str2bool, default=False, help="Clean images above cache level"
#     )
#     parser.add_argument("--session_id", type=str, help="Session ID")
#     args = parser.parse_args()

#     main(**vars(args))
