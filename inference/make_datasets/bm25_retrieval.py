import json
import os
import ast
import jedi
import traceback
import subprocess
import time
import shutil
import numpy as np
from multiprocessing import Process, Lock, Value, Manager, set_start_method
from pyserini.search.lucene import LuceneSearcher
from git import Repo
from pathlib import Path
from .utils import ContextManager, is_test, list_files
from tqdm.auto import tqdm
from argparse import ArgumentParser
from tempfile import TemporaryDirectory
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def file_name_and_contents(filename, relative_path):
    text = relative_path + "\n"
    with open(filename, "r") as f:
        text += f.read()
    return text


def file_name_and_documentation(filename, relative_path):
    text = relative_path + "\n"
    try:
        with open(filename, "r") as f:
            node = ast.parse(f.read())

        # Get module docstring
        data = ast.get_docstring(node)
        if data:
            text += f"{data}"

        # Walk through all nodes in the AST
        for child_node in ast.walk(node):
            if isinstance(
                child_node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                data = ast.get_docstring(child_node)
                if data:
                    text += f"\n\n{child_node.name}\n{data}"
    except Exception as e:
        logger.error(e)
        logger.error(f"Failed to parse file {str(filename)}. Using simple filecontent.")
        with open(filename, "r") as f:
            text += f.read()
    return text


def file_name_and_docs_jedi(filename, relative_path):
    text = relative_path + "\n"
    with open(filename, "r") as f:
        source_code = f.read()
    try:
        script = jedi.Script(source_code, path=filename)
        module = script.get_context()
        docstring = module.docstring()
        text += f"{module.full_name}\n"
        if docstring:
            text += f"{docstring}\n\n"
        abspath = Path(filename).absolute()
        names = [
            name
            for name in script.get_names(
                all_scopes=True, definitions=True, references=False
            )
            if not name.in_builtin_module()
        ]
        for name in names:
            try:
                origin = name.goto(follow_imports=True)[0]
                if origin.module_name != module.full_name:
                    continue
                if name.parent().full_name != module.full_name:
                    if name.type in {"statement", "param"}:
                        continue
                full_name = name.full_name
                text += f"{full_name}\n"
                docstring = name.docstring()
                if docstring:
                    text += f"{docstring}\n\n"
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            except:
                continue
    except KeyboardInterrupt:
        raise KeyboardInterrupt
    except Exception as e:
        logger.error(e)
        logger.error(f"Failed to parse file {str(filename)}. Using simple filecontent.")
        text = f"{relative_path}\n{source_code}"
        return text
    return text


DOCUMENT_ENCODING_FUNCTIONS = {
    "file_name_and_contents": file_name_and_contents,
    "file_name_and_documentation": file_name_and_documentation,
    "file_name_and_docs_jedi": file_name_and_docs_jedi,
}


def clone_repo(repo, root_dir, token, from_swebench, thread_id):
    thread_prefix = f'(thread #{thread_id}) (pid {os.getpid()}) '
    repo_dir = os.path.join(root_dir, repo.replace("/", "__"))
    if not os.path.exists(repo_dir):
        if from_swebench:
            repo_url = (
                f"https://{token}@github.com/swe-bench/"
                + repo.replace("/", "__")
                + ".git"
            )
        else:
            repo_url = f"https://{token}@github.com/{repo}.git"
        logger.info(thread_prefix + f"Cloning {repo}")
        Repo.clone_from(repo_url, repo_dir)
    return repo_dir


def build_documents(repo_dir, commit, document_encoding_func):
    documents = dict()
    with ContextManager(repo_dir, commit) as cm:
        filenames = list_files(cm.repo_path, include_tests=False)
        for relative_path in filenames:
            filename = Path(relative_path).absolute()
            text = document_encoding_func(filename, relative_path)
            documents[relative_path] = text
    return documents


def make_index(repo_dir, root_dir, commit, document_encoding_func, python, thread_id, instance_id):
    index_path = Path(root_dir, str(instance_id), "index")
    if index_path.exists():
        return index_path
    thread_prefix = f'(thread #{thread_id}) (pid {os.getpid()}) '
    documents_path = Path(root_dir, instance_id, "documents.jsonl")
    if not documents_path.parent.exists():
        documents_path.parent.mkdir(parents=True)
    documents = build_documents(repo_dir, commit, document_encoding_func)
    with open(documents_path, "w") as docfile:
        for relative_path, contents in documents.items():
            print(
                json.dumps({"id": relative_path, "contents": contents}),
                file=docfile,
                flush=True,
            )
    output = subprocess.run(
        [
            python,
            "-m",
            "pyserini.index",
            "--collection",
            "JsonCollection",
            "--generator",
            "DefaultLuceneDocumentGenerator",
            "--threads",
            "2",
            "--input",
            documents_path.parent.as_posix(),
            "--index",
            index_path.as_posix(),
            "--storePositions",
            "--storeDocvectors",
            "--storeRaw",
        ],
        check=False,
        capture_output=True,
    )
    if output.returncode == 130:
        raise KeyboardInterrupt
    if output.returncode != 0:
        logger.error(thread_prefix + output.stderr.decode("utf-8"))
        raise Exception(thread_prefix + f"Failed to build index for {instance_id}")
        return None
    logger.info(thread_prefix + f"Finished indexing {index_path}")
    return index_path


def make_indexes(
    root_dir,
    instances,
    document_encoding_func,
    python,
    from_swebench,
    token,
    counter,
    counter_lock,
    thread_id,
    index_paths,
):
    tmp_dir = TemporaryDirectory(dir=root_dir)
    thread_prefix = f'(thread #{thread_id}) (pid {os.getpid()}) '
    for instance in instances:
        repo = instance["repo"]
        commit = instance["base_commit"]
        instance_id = instance["instance_id"]
        try:
            repo_dir = clone_repo(repo, tmp_dir.name, token, from_swebench, thread_id)
            index_path = make_index(
                repo_dir, root_dir, commit, document_encoding_func, python, thread_id, instance_id
            )
            if index_path is None:
                continue
            index_paths[instance_id] = index_path
        except KeyboardInterrupt:
            logger.info(thread_prefix + "KeyboardInterrupt received. Terminating.")
            break
        except:
            logger.error(
                thread_prefix + f"Failed to process {repo}/{commit} (instance {instance_id})"
            )
            logger.error(thread_prefix + traceback.format_exc())
            continue
        with counter_lock:
            counter.value += 1
    tmp_dir.cleanup()
    return index_paths


def get_remaining_instances(instances, output_file):
    instance_ids = set()
    remaining_instances = list()
    if output_file.exists():
        with open(output_file, "r") as f:
            for line in f:
                instance = json.loads(line)
                instance_id = instance["instance_id"]
                instance_ids.add(instance_id)
        logger.warning(
            f"Found {len(instance_ids)} existing instances in {output_file}. Will skip them."
        )
    else:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        return instances
    for instance in instances:
        instance_id = instance["instance_id"]
        if instance_id not in instance_ids:
            remaining_instances.append(instance)
    return remaining_instances


def chunk_list(l, n):
    for i in range(0, len(l), n):
        yield l[i : i + n]


def monitor(counter, lock, total):
    pid = os.getpid()
    # if this doesn't disappear, kill the process
    with tqdm(total=total, desc=f'Monitoring (pid {pid})') as pbar:
        while counter.value < total:
            with lock:
                pbar.n = counter.value
                pbar.refresh()
            time.sleep(2)


def search(instance, index_path):
    try:
        instance_id = instance["instance_id"]
        searcher = LuceneSearcher(index_path.as_posix())
        cutoff = len(instance["problem_statement"])
        while True:
            try:
                hits = searcher.search(
                    instance["problem_statement"][:cutoff],
                    k=20,
                    remove_dups=True,
                )
            except Exception as e:
                if "maxClauseCount" in str(e):
                    cutoff = int(round(cutoff * 0.8))
                    continue
                else:
                    raise e
            break
        results = {"instance_id": instance_id, "hits": []}
        for hit in hits:
            results["hits"].append({"docid": hit.docid, "score": hit.score})
        return results
    except Exception as e:
        logger.error(
            f"Failed to process {instance_id}"
        )
        logger.error(traceback.format_exc())
        return None
    

def search_indexes(remaining_instance, output_file, all_index_paths):
    with open(output_file, "a") as out_file:
        for instance in tqdm(remaining_instance, desc="Retrieving"):
            instance_id = instance["instance_id"]
            if instance_id not in all_index_paths:
                continue
            index_path = all_index_paths[instance_id]
            results = search(instance, index_path)
            if results is None:
                continue
            print(json.dumps(results), file=out_file, flush=True)


def get_missing_ids(instances, output_file):
    with open(output_file, "r") as f:
        written_ids = set()
        for line in f:
            instance = json.loads(line)
            instance_id = instance["instance_id"]
            written_ids.add(instance_id)
    missing_ids = set()
    for instance in instances:
        instance_id = instance["instance_id"]
        if instance_id not in written_ids:
            missing_ids.add(instance_id)
    return missing_ids


def get_index_paths(
        remaining_instances,
        root_dir_name,
        document_encoding_func,
        python,
        from_swebench,
        token,
        num_workers,
):
    instances_chunks = list(
        chunk_list(remaining_instances, int(np.ceil(len(remaining_instances) / num_workers)))
    )
    total_work = len(remaining_instances)
    with Manager() as manager:
        counter = manager.Value("i", 0)
        counter_lock = manager.Lock()
        all_index_paths = manager.dict()
        processes = list()
        for ix, instances_chunk in enumerate(instances_chunks):
            p = Process(
                target=make_indexes,
                args=(
                    root_dir_name,
                    instances_chunk,
                    document_encoding_func,
                    python,
                    from_swebench,
                    token,
                    counter,
                    counter_lock,
                    ix,
                    all_index_paths,
                ),
            )
            processes.append(p)
        monitor_process = Process(
                target=monitor,
                args=(counter, counter_lock, total_work),
            )
        for p in processes:
            p.start()
        monitor_process.start()
        for p in processes:
            p.join()
        if monitor_process.is_alive():
            monitor_process.terminate()
    return all_index_paths

def get_root_dir(use_tmp, output_dir, document_encoding_style):
    if use_tmp:
        tmp_root = "/scratch" if os.path.exists("/scratch") else "/tmp"
        root_dir = TemporaryDirectory(dir=tmp_root)
        root_dir_name = root_dir.name
    else:
        root_dir = Path(output_dir, document_encoding_style + "_indexes")
        if not root_dir.exists():
            root_dir.mkdir(parents=True, exist_ok=True)
        root_dir_name = root_dir
    return root_dir, root_dir_name


def main(instances_files, document_encoding_style, from_swebench, output_dir, use_tmp, num_workers):
    set_start_method('fork')
    document_encoding_func = DOCUMENT_ENCODING_FUNCTIONS[document_encoding_style]
    token = os.environ.get("GITHUB_TOKEN", "git")
    instances = list()
    for instances_file in instances_files:
        instances += [json.loads(line) for line in open(instances_file)]
    python = subprocess.run("which python", shell=True, capture_output=True)
    python = python.stdout.decode("utf-8").strip()
    output_file = Path(output_dir, document_encoding_style + ".retrieval.jsonl")
    remaining_instances = get_remaining_instances(instances, output_file)
    root_dir, root_dir_name = get_root_dir(use_tmp, output_dir, document_encoding_style)
    all_index_paths = get_index_paths(
        remaining_instances,
        root_dir_name,
        document_encoding_func,
        python,
        from_swebench,
        token,
        num_workers,
    )
    logger.info(f"Finished indexing {len(all_index_paths)} instances")
    search_indexes(remaining_instances, output_file, all_index_paths)
    missing_ids = get_missing_ids(instances, output_file)
    logger.info(f"Missing indexes for {len(missing_ids)} instances.\n{missing_ids}")
    logger.info(f"Saved retrieval results to {output_file}")
    if isinstance(root_dir, TemporaryDirectory):
        root_dir.cleanup()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--instances_files", nargs="+", required=True)
    parser.add_argument(
        "--document_encoding_style",
        required=True,
        choices=DOCUMENT_ENCODING_FUNCTIONS.keys(),
    )
    parser.add_argument("--from_swebench", action="store_true")
    parser.add_argument("--use_tmp", action="store_true")
    parser.add_argument("--output_dir", default="./retreival_results")
    parser.add_argument("--num_workers", type=int, default=4)
    args = parser.parse_args()
    main(**vars(args))
