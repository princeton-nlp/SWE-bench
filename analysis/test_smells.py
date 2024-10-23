import os
import subprocess
import re

from datasets import load_dataset

from argparse import ArgumentParser

def create_smell_command(instance_id, logs_dir, test_path) -> list:
    command = ["pytest-smell"]
    if logs_dir:
        instance_dir = os.path.join(logs_dir, instance_id)
        if not os.path.exists(instance_dir):
            os.mkdir(instance_dir)
        command.append(f"--out_path={instance_dir}")
    if test_path:
        command.append(f"--tests_path={test_path}")
    return command

def create_playground(repo: str, commit_sha: str):
    rel_repo_path = repo.split("/")[-1]
    if not os.path.exists(rel_repo_path):
        print(f"repo {repo} does not exist. Cloning now...")
        subprocess.run(["git", "clone", f"https://github.com/{repo}.git"], check=True)
    else:
        print(f"repo {repo} already exists. Skipping cloning.")
    
    os.chdir(rel_repo_path)
    
    subprocess.run(["git", "reset", "--hard"])
    subprocess.run(["git", "fetch", "--all"], check=True)
    subprocess.run(["git", "checkout", commit_sha], check=True)

    print(f"Checked out commit {commit_sha} in {repo} and changed directory to {rel_repo_path}")

def extract_paths_from_diff(diff_str):
    pattern = r"^diff --git a/(\S+) b/\S+"
    matches = re.findall(pattern, diff_str, re.MULTILINE)

    def extract_path_until_test(path):
        parts = path.split(os.sep)
        for i, part in enumerate(parts):
            if 'test' in part.lower():
                return os.sep.join(parts[:i + 1])
        return path

    return [extract_path_until_test(match) for match in matches]

def write_diff_to_patch(diff_str, patch_file_path):
    try:
        with open(patch_file_path, 'w') as patch_file:
            patch_file.write(diff_str)
        print(f"Patch file written to: {patch_file_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

def test_smeller(dataset_name, playground_dir, logs_dir):
    if not os.path.exists(playground_dir):
        print(f"directory {playground_dir} does not exist. Creating now...")
        os.makedirs(playground_dir)
    if not os.path.exists(logs_dir):
        print(f"directory {logs_dir} does not exist. Creating now...")
        os.makedirs(logs_dir)

    playground_dir = os.path.abspath(playground_dir)
    logs_dir = os.path.abspath(logs_dir)

    dataset = load_dataset(dataset_name, split="test")

    for data in dataset:
        os.chdir(playground_dir)
        create_playground(data["repo"], data["base_commit"])
        temp_patch = write_diff_to_patch(data["test_patch"], "temp.patch")
        subprocess.run(["git", "apply", "temp.patch"])
        test_folder_path = extract_paths_from_diff(data["test_patch"])[0]
        test_smell_command = create_smell_command(data["instance_id"], logs_dir, test_folder_path)
        subprocess.run(test_smell_command)

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--dataset_name", default="princeton-nlp/SWE-bench_Verified", type=str, help="Name of dataset or path to JSON file.")
    parser.add_argument("--playground_dir", default="./analysis/playground", type=str)
    parser.add_argument("--logs_dir", default="./analysis/smell_logs", type=str)
    args = parser.parse_args()

    test_smeller(**vars(args))