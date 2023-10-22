import os
import re
import ast
import chardet
import subprocess
import base64
import unidiff
from argparse import ArgumentTypeError
from git import Repo
from ghapi.all import GhApi
from pathlib import Path
from tempfile import TemporaryDirectory


DIFF_PATTERN = re.compile(r"^diff(?:.*)")
PATCH_PATTERN = re.compile(
    r"(?:diff[\w\_\.\ \/\-]+\n)?\-\-\-\s+a\/(?:.*?)\n\+\+\+\s+b\/(?:.*?)(?=diff\ |\-\-\-\ a\/|\Z)",
    re.DOTALL,
)
PATCH_FILE_PATTERN = re.compile(r"\-\-\-\s+a\/(?:.+)\n\+\+\+\s+b\/(?:.+)")
PATCH_HUNK_PATTERN = re.compile(
    r"\@\@\s+\-(\d+),(\d+)\s+\+(\d+),(\d+)\s+\@\@(.+?)(?=diff\ |\-\-\-\ a\/|\@\@\ \-|\Z)",
    re.DOTALL,
)


def get_first_idx(charlist):
    first_min = charlist.index("-") if "-" in charlist else len(charlist)
    first_plus = charlist.index("+") if "+" in charlist else len(charlist)
    return min(first_min, first_plus)


def get_last_idx(charlist):
    char_idx = get_first_idx(charlist[::-1])
    last_idx = len(charlist) - char_idx
    return last_idx + 1


def strip_content(hunk):
    first_chars = list(map(lambda x: None if not len(x) else x[0], hunk.split("\n")))
    first_idx = get_first_idx(first_chars)
    last_idx = get_last_idx(first_chars)
    new_lines = list(map(lambda x: x.rstrip(), hunk.split("\n")[first_idx:last_idx]))
    new_hunk = "\n" + "\n".join(new_lines) + "\n"
    return new_hunk, first_idx - 1


def get_hunk_stats(pre_start, pre_len, post_start, post_len, hunk, total_delta):
    stats = {"context": 0, "added": 0, "subtracted": 0}
    hunk = hunk.split("\n", 1)[-1].strip("\n")
    for line in hunk.split("\n"):
        if line.startswith("-"):
            stats["subtracted"] += 1
        elif line.startswith("+"):
            stats["added"] += 1
        else:
            stats["context"] += 1
    context = stats["context"]
    added = stats["added"]
    subtracted = stats["subtracted"]
    pre_len = context + subtracted
    post_start = pre_start + total_delta
    post_len = context + added
    total_delta = total_delta + (post_len - pre_len)
    return pre_start, pre_len, post_start, post_len, total_delta


def repair_patch(model_patch):
    if model_patch is None:
        return None
    model_patch = model_patch.lstrip("\n")
    new_patch = ""
    for patch in PATCH_PATTERN.findall(model_patch):
        total_delta = 0
        diff_header = DIFF_PATTERN.findall(patch)
        if diff_header:
            new_patch += diff_header[0] + "\n"
        patch_header = PATCH_FILE_PATTERN.findall(patch)[0]
        if patch_header:
            new_patch += patch_header + "\n"
        for hunk in PATCH_HUNK_PATTERN.findall(patch):
            pre_start, pre_len, post_start, post_len, content = hunk
            pre_start, pre_len, post_start, post_len, total_delta = get_hunk_stats(
                *list(map(lambda x: int(x) if x.isnumeric() else x, hunk)), total_delta
            )
            new_patch += (
                f"@@ -{pre_start},{pre_len} +{post_start},{post_len} @@{content}"
            )
    return new_patch


def extract_minimal_patch(model_patch):
    model_patch = model_patch.lstrip("\n")
    new_patch = ""
    for patch in PATCH_PATTERN.findall(model_patch):
        total_delta = 0
        diff_header = DIFF_PATTERN.findall(patch)
        patch_header = PATCH_FILE_PATTERN.findall(patch)[0]
        if patch_header:
            new_patch += patch_header + "\n"
        for hunk in PATCH_HUNK_PATTERN.findall(patch):
            pre_start, pre_len, post_start, post_len, content = hunk
            pre_start, pre_len, post_start, post_len, content = list(
                map(lambda x: int(x) if x.isnumeric() else x, hunk)
            )
            content, adjust_pre_start = strip_content(content)
            pre_start += adjust_pre_start
            pre_start, pre_len, post_start, post_len, total_delta = get_hunk_stats(
                pre_start, pre_len, post_start, post_len, content, total_delta
            )
            new_patch += (
                f"@@ -{pre_start},{pre_len} +{post_start},{post_len} @@{content}"
            )
    return new_patch


def extract_diff(response):
    """
    Extracts the diff from a response formatted in different ways
    """
    if response is None:
        return None
    diff_matches = []
    other_matches = []
    pattern = re.compile(r"\<([\w-]+)\>(.*?)\<\/\1\>", re.DOTALL)
    for code, match in pattern.findall(response):
        if code in {"diff", "patch"}:
            diff_matches.append(match)
        else:
            other_matches.append(match)
    pattern = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)
    for code, match in pattern.findall(response):
        if code in {"diff", "patch"}:
            diff_matches.append(match)
        else:
            other_matches.append(match)
    if diff_matches:
        return diff_matches[0]
    if other_matches:
        return other_matches[0]
    return response.split("</s>")[0]


def is_test(name, test_phrases=None):
    if test_phrases is None:
        test_phrases = ["test", "tests", "testing"]
    words = set(re.split(r" |_|\/|\.", name.lower()))
    return any(word in words for word in test_phrases)


class ContextManager:
    def __init__(self, repo_path, base_commit, verbose=False):
        self.repo_path = Path(repo_path).resolve().as_posix()
        self.old_dir = os.getcwd()
        self.base_commit = base_commit
        self.verbose = verbose

    def __enter__(self):
        os.chdir(self.repo_path)
        cmd = f"git reset --hard {self.base_commit} && git clean -fdxq"
        if self.verbose:
            subprocess.run(cmd, shell=True, check=True)
        else:
            subprocess.run(
                cmd,
                shell=True,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return self

    def get_environment(self):
        raise NotImplementedError()  # TODO: activate conda environment and return the environment file

    def get_readme_files(self):
        files = os.listdir(self.repo_path)
        files = list(filter(lambda x: os.path.isfile(x), files))
        files = list(filter(lambda x: x.lower().startswith("readme"), files))
        return files

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.chdir(self.old_dir)


class AutoContextManager(ContextManager):
    """Automatically clones the repo if it doesn't exist"""

    def __init__(self, instance, root_dir=None, verbose=False, token=None):
        if token is None:
            token = os.environ.get("GITHUB_TOKEN", "git")
        self.tempdir = None
        if root_dir is None:
            self.tempdir = TemporaryDirectory()
            root_dir = self.tempdir.name
        self.root_dir = root_dir
        repo_dir = os.path.join(self.root_dir, instance["repo"].replace("/", "__"))
        if not os.path.exists(repo_dir):
            repo_url = (
                f"https://{token}@github.com/swe-bench/"
                + instance["repo"].replace("/", "__")
                + ".git"
            )
            if verbose:
                print(f"Cloning {instance['repo']} to {root_dir}")
            Repo.clone_from(repo_url, repo_dir)
        super().__init__(repo_dir, instance["base_commit"], verbose=verbose)
        self.instance = instance

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.tempdir is not None:
            self.tempdir.cleanup()
        return super().__exit__(exc_type, exc_val, exc_tb)


def get_imported_modules(filename):
    with open(filename, "rt") as file:
        tree = ast.parse(file.read(), filename)
    return [
        node
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]


def resolve_module_to_file(module, level, root_dir):
    components = module.split(".")
    if level > 0:
        components = components[:-level]
    for dirpath, dirnames, filenames in os.walk(root_dir):
        if dirpath.endswith(os.sep.join(components)):
            return [
                os.path.join(dirpath, filename)
                for filename in filenames
                if filename.endswith(".py")
            ]
    return []


def ingest_file_directory_contents(target_file, root_dir):
    imported_files = []
    files_to_check = [target_file]
    while files_to_check:
        current_file = files_to_check.pop()
        imported_files.append(current_file)
        imports = get_imported_modules(current_file)
        for node in imports:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    files = resolve_module_to_file(alias.name, 0, root_dir)
                    for file in files:
                        if file not in imported_files and file not in files_to_check:
                            files_to_check.append(file)
            elif isinstance(node, ast.ImportFrom):
                files = resolve_module_to_file(node.module, node.level, root_dir)
                for file in files:
                    if file not in imported_files and file not in files_to_check:
                        files_to_check.append(file)
    return imported_files


def detect_encoding(filename):
    """
    Detect the encoding of a file
    """
    with open(filename, "rb") as file:
        rawdata = file.read()
    return chardet.detect(rawdata)["encoding"]


def list_files(root_dir, include_tests=False):
    files = []
    for filename in Path(root_dir).rglob("*.py"):
        if not include_tests and is_test(filename.as_posix()):
            continue
        files.append(filename.relative_to(root_dir).as_posix())
    return files


def ingest_directory_contents(root_dir, include_tests=False):
    files_content = {}
    for relative_path in list_files(root_dir, include_tests=include_tests):
        filename = os.path.join(root_dir, relative_path)
        encoding = detect_encoding(filename)
        if encoding is None:
            content = "[BINARY DATA FILE]"
        else:
            try:
                with open(filename, "r", encoding=encoding) as file:
                    content = file.read()
            except (UnicodeDecodeError, LookupError):
                content = "[BINARY DATA FILE]"
        files_content[relative_path] = content
    return files_content


def string_to_bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise ArgumentTypeError(
            f"Truthy value expected: got {v} but expected one of yes/no, true/false, t/f, y/n, 1/0 (case insensitive)."
        )


def convert_patch_to_simple_patch(patch):
    """
    Converts a patch to a simple patch.

    Args:
        patch (str): The patch to convert.

    Returns:
        str: The converted patch.
    """
    patchset = unidiff.PatchSet(patch)
    data = []
    for file in patchset:
        source_file = file.source_file.split("a/", 1)[-1]
        target_file = file.target_file.split("b/", 1)[-1]
        data.append("source_file: " + source_file)
        data.append("target_file: " + target_file)
        for hunk in file:
            data.append("@@ source_start: " + str(hunk.source_start))
            for line in hunk:
                linetype = line.line_type.replace(" ", "*")
                if linetype in {"*", "-"}:
                    data.append(linetype + " " + str(line.source_line_no))
                else:
                    assert linetype == "+"
                    data.append(linetype + " " + line.value.rstrip("\n"))
        data.append("@@ ---")
    return "\n".join(data)


def get_file_from_repo(owner, repo, base_commit_hash, filepath):
    api = GhApi(token=os.environ.get("GITHUB_TOKEN", None))
    file_info = api.repos.get_content(owner, repo, filepath, ref=base_commit_hash)
    file_content = base64.b64decode(file_info.content).decode("utf-8")
    return file_content


def convert_simple_patch_to_patch(simple_patch, instance):
    """
    Convert a simple patch to a full patch.

    Args:
        simple_patch (str): The simple patch to convert.
        instance (dict): A dictionary containing information about the repository and commit.

    Returns:
        str: The full patch.
    """
    pat = re.compile(
        r"source_file:\s+(.+?)\ntarget_file:\s+(.+?)\n(.*?)(?=source_file:\s+|@@\ ---|$)",
        re.DOTALL,
    )
    hunk_pattern = re.compile(
        r"@@\s+source_start:\s+(\d+)\n(.*?)(?=\n@@\s+source_start:\s+|\n@@\ ---|$)",
        re.DOTALL,
    )
    line_pattern = re.compile(r"([\+\-\*])\ (.*)")
    owner, repo = instance["repo"].split("/")
    base_commit = instance["base_commit"]
    diff = list()
    for filediff in pat.findall(simple_patch):
        source_file, target_file, content = filediff
        diff.append(f"diff --git a/{source_file} b/{target_file}")
        diff.append(f"--- a/{source_file}")
        diff.append(f"+++ b/{target_file}")
        source_file_contents = get_file_from_repo(
            owner, repo, base_commit, source_file
        ).split("\n")
        target_offset = 0
        for start_line, hunk in hunk_pattern.findall(content):
            source_lines = 0
            target_lines = 0
            hunk_data = list()
            for line_type, line in line_pattern.findall(hunk):
                if line_type == "*":
                    lineno = int(line) - 1
                    hunk_data.append(f" {source_file_contents[lineno]}")
                    source_lines += 1
                    target_lines += 1
                elif line_type == "-":
                    lineno = int(line) - 1
                    hunk_data.append(f"-{source_file_contents[lineno]}")
                    source_lines += 1
                else:
                    assert line_type == "+"
                    hunk_data.append(f"+{line}")
                    target_lines += 1
            header = f"@@ -{start_line},{source_lines} +{int(start_line) + target_offset},{target_lines} @@"
            target_offset += target_lines - source_lines
            diff.append(header)
            diff.extend(hunk_data)
    return "\n".join(diff) + "\n"
