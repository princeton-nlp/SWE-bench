import json
import logging
import os
import traceback
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unidiff
from tqdm.auto import tqdm

try:
    from tokenize_dataset import TOKENIZER_FUNCS
    from utils import AutoContextManager, ingest_directory_contents
except:
    from .tokenize_dataset import TOKENIZER_FUNCS
    from .utils import AutoContextManager, ingest_directory_contents

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


FILE_CONTENTS_EXAMPLE = """[start of euclidean.py]
def euclidean(a, b):
    if b == 0:
        return a
    return euclidean(b, a % b)
[end of euclidean.py]]
[start of bresenham.py]
def bresenham(x0, y0, x1, y1):
    dx = x1 - x0
    dy = y1 - y0

    xsign = 1 if dx > 0 else -1
    ysign = 1 if dy > 0 else -1

    dx = abs(dx)
    dy = abs(dy)

    if dx > dy:
        xx, xy, yx, yy = xsign, 0, 0, ysign
    else:
        dx, dy = dy, dx
        xx, xy, yx, yy = 0, ysign, xsign, 0

    D = 2*dy - dx
    y = 0

    for x in range(dx + 1):
        yield x0 + x*xx + y*yx, y0 + x*xy + y*yy
        if D > 0:
            y += 1
            D -= dx
        D += dy
[end of bresenham.py]"""


PATCH_EXAMPLE = """diff --git a/bresenham.py b/bresenham.py
--- a/bresenham.py
+++ b/bresenham.py
@@ -1,6 +1,6 @@
 def bresenham(x0, y0, x1, y1):
     dx = x1 - x0
-    dy = y1 - y0
+    dy = y1 - y0 # add a comment

     xsign = 1 if dx > 0 else -1
     ysign = 1 if dy > 0 else -1
@@ -19,7 +19,7 @@ def bresenham(x0, y0, x1, y1):

     for x in range(dx + 1):
         yield x0 + x*xx + y*yx, y0 + x*xy + y*yy
-        if D > 0:
+        if D >= 0:
             y += 1
-            D -= dx
-        D += dy
+            D -= 2*dx
+        D += 2*dy
diff --git a/euclidean.py b/euclidean.py
--- a/euclidean.py
+++ b/euclidean.py
@@ -1,4 +1,4 @@
 def euclidean(a, b):
-    if b == 0:
-        return a
-    return euclidean(b, a % b)
+    while b != 0:
+        a, b = b, a % b
+    return a
"""


SIMPLE_PATCH_EXAMPLE = """source_file: bresenham.py
target_file: bresenham.py
@@ source_start: 1
* 1
* 2
- 3
+    dy = y1 - y0 # add a comment
* 4
* 5
* 6
@@ source_start: 19
* 19
* 20
* 21
- 22
+        if D >= 0:
* 23
- 24
- 25
+            D -= 2*dx
+        D += 2*dy
@@ ---
source_file: euclidean.py
target_file: euclidean.py
@@ source_start: 1
* 1
- 2
- 3
- 4
+    while b != 0:
+        a, b = b, a % b
+    return a
@@ ---
"""


CONTEXT_PATCH_EXAMPLE = """source_file: bresenham.py
target_file: bresenham.py
@@ source_start: 1
*def bresenham(x0, y0, x1, y1):
*    dx = x1 - x0
-    dy = y1 - y0
+    dy = y1 - y0 # add a comment
*
*    xsign = 1 if dx > 0 else -1
*    ysign = 1 if dy > 0 else -1
@@ source_start: 19
*
*    for x in range(dx + 1):
*        yield x0 + x*xx + y*yx, y0 + x*xy + y*yy
-        if D > 0:
+        if D >= 0:
*            y += 1
-            D -= dx
-        D += dy
+            D -= 2*dx
+        D += 2*dy
@@ ---
source_file: euclidean.py
target_file: euclidean.py
@@ source_start: 1
*def euclidean(a, b):
-    if b == 0:
-        return a
-    return euclidean(b, a % b)
+    while b != 0:
+        a, b = b, a % b
+    return a
@@ ---
"""


FULL_GENERATION_EXAMPLE = """[start of bresenham.py]
def bresenham(x0, y0, x1, y1):
    dx = x1 - x0
    dy = y1 - y0

    xsign = 1 if dx > 0 else -1
    ysign = 1 if dy > 0 else -1

    dx = abs(dx)
    dy = abs(dy)

    if dx > dy:
        xx, xy, yx, yy = xsign, 0, 0, ysign
    else:
        dx, dy = dy, dx
        xx, xy, yx, yy = 0, ysign, xsign, 0

    D = 2*dy - dx
    y = 0

    for x in range(dx + 1):
        yield x0 + x*xx + y*yx, y0 + x*xy + y*yy
        if D >= 0:
            y += 1
            D -= 2*dx
        D += 2*dy
[end of bresenham.py]
[start of euclidean.py]
def euclidean(a, b):
    while b != 0:
        a, b = b, a % b
    return a
[end of euclidean.py]"""


def add_lines_list(content):
    content_with_lines = list()
    for ix, line in enumerate(content.split("\n"), start=1):
        content_with_lines.append(f"{ix} {line}")
    return content_with_lines


def add_lines(content):
    return "\n".join(add_lines_list(content))


def make_code_text(files_dict, add_line_numbers=True):
    all_text = ""
    for filename, contents in sorted(files_dict.items()):
        all_text += f"[start of {filename}]\n"
        if add_line_numbers:
            all_text += add_lines(contents)
        else:
            all_text += contents
        all_text += f"\n[end of {filename}]\n"
    return all_text.strip("\n")


def make_code_text_edits_only(files_dict, patch, add_line_numbers=True):
    files = dict()
    patch = unidiff.PatchSet(patch)
    for patched_file in patch:
        source_file = patched_file.source_file.split("a/", 1)[-1]
        files[source_file] = list()
        for hunk in patched_file:
            start = hunk.source_start - 15
            end = start + hunk.source_length + 15
            files[source_file].append((start, end))
    all_text = ""
    for filename, content in files_dict.items():
        all_text += f"[start of {filename}]\n"
        content_with_lines = add_lines_list(content)
        for start, end in files[filename]:
            if start > 0:
                all_text += "...\n"
            all_text += "\n".join(content_with_lines[start:end])
            all_text += "\n"
            if end < len(content_with_lines):
                all_text += "...\n"
        all_text = all_text.strip("\n")
        all_text += f"\n[end of {filename}]\n"
    return all_text.strip("\n")


def prompt_style_2(instance):
    premise = "You will be provided with a partial code base and an issue statement explaining a problem to resolve."
    readmes_text = make_code_text(instance["readmes"])
    code_text = make_code_text(instance["file_contents"])
    instructions = (
        f"I need you to solve this issue by generating a single patch file that I can apply "
        + f"directly to this repository using git apply. Please respond with a single patch "
        + f"file in the following format."
    )
    problem_statement = instance["problem_statement"]
    final_text = [
        premise,
        "<issue>",
        problem_statement,
        "</issue>",
        "<code>",
        readmes_text,
        code_text,
        "</code>",
        instructions,
        "<patch>",
        PATCH_EXAMPLE,
        "</patch>",
    ]
    final_text = "\n".join(final_text)
    return final_text


def prompt_style_2_edits_only(instance):
    premise = "You will be provided with a partial code base and an issue statement explaining a problem to resolve."
    readmes_text = make_code_text(instance["readmes"])
    code_text = make_code_text_edits_only(instance["file_contents"], instance["patch"])
    instructions = (
        f"I need you to solve this issue by generating a single patch file that I can apply "
        + f"directly to this repository using git apply. Please respond with a single patch "
        + f"file in the following format."
    )
    problem_statement = instance["problem_statement"]
    final_text = [
        premise,
        "<issue>",
        problem_statement,
        "</issue>",
        "<code>",
        readmes_text,
        code_text,
        "</code>",
        instructions,
        "<patch>",
        PATCH_EXAMPLE,
        "</patch>",
    ]
    final_text = "\n".join(final_text)
    return final_text


def prompt_style_3(instance):
    premise = "You will be provided with a partial code base and an issue statement explaining a problem to resolve."
    readmes_text = make_code_text(instance["readmes"])
    code_text = make_code_text(instance["file_contents"])
    example_explanation = (
        f"Here is an example of a patch file. It consists of changes to the code base. "
        + f"It specifies the file names, the line numbers of each change, and the removed and added lines. "
        + f"A single patch file can contain changes to multiple files."
    )
    final_instruction = (
        f"I need you to solve the provded issue by generating a single patch file that I can apply "
        + f"directly to this repository using git apply. Please respond with a single patch "
        + f"file in the format shown above."
    )
    problem_statement = instance["problem_statement"]
    final_text = [
        premise,
        "<issue>",
        problem_statement,
        "</issue>",
        "",
        "<code>",
        readmes_text,
        code_text,
        "</code>",
        "",
        example_explanation,
        "<patch>",
        PATCH_EXAMPLE,
        "</patch>",
        "",
        final_instruction,
        "Respond below:",
    ]
    final_text = "\n".join(final_text)
    return final_text


def full_file_gen(instance):
    premise = "You will be provided with a partial code base and an issue statement explaining a problem to resolve."
    readmes_text = make_code_text(instance["readmes"], add_line_numbers=False)
    code_text = make_code_text(instance["file_contents"], add_line_numbers=False)
    instructions = (
        f"I need you to solve this issue by regenerating the full files in the code base that you would like to change. "
        + f"You can change as many files as you like. "
        + f"Please respond with a list of files and their revised contents in the following format."
    )
    problem_statement = instance["problem_statement"]
    final_text = [
        premise,
        "<issue>",
        problem_statement,
        "</issue>",
        "<code>",
        readmes_text,
        code_text,
        "</code>",
        instructions,
        "<example>",
        FULL_GENERATION_EXAMPLE,
        "</example>",
    ]
    final_text = "\n".join(final_text)
    return final_text


def prompt_style_5(instance):
    premise = "You will be provided with a partial code base and an issue from GitHub explaining a problem to resolve."
    readmes_text = make_code_text(instance["readmes"])
    code_text = make_code_text(instance["file_contents"])
    instructions = (
        f"I need you to solve this issue by generating a specialized patch file that I can apply "
        + f"directly to this repository using git apply. Please respond with a single patch "
        + f"file in the following format."
    )
    instructions = (
        f"I need you to solve this issue by generating a specially formatted patch file that I can process and apply "
        + f"directly to this repository. Your response should be a single patch file in the following format.\n"
        + f"Given the following files:"
    )
    post_instructions = f"You can edit them as follows:"
    format_explanation = (
        f"In the patch file format, you can specify the source and target file for the following changes using "
        + f"\nsource_file: <source_file_name>\ntarget_file: <target_file_name>\n"
        + f"@@ source_start: <source_start_line_number> specifies the beginning of a change in the source file.\n"
        + f"@@ --- specifies the end of a change in the source file.\n"
        + f"Lines can either be unchanged (prefixed with *), removed (prefixed with -), or added (prefixed with +).\n"
        + f"Unchanged or removed lines are specified simply by their line number.\n"
        + f"You can make multiple changes per file, and multiple files per patch file."
    )
    prompt = 'Respond below:'
    problem_statement = instance["problem_statement"]
    final_text = [
        premise,
        "<issue>",
        problem_statement,
        "</issue>",
        "<code>",
        readmes_text,
        code_text,
        "</code>",
        instructions,
        "<example>",
        FILE_CONTENTS_EXAMPLE,
        "</example>",
        post_instructions,
        "<patch>",
        SIMPLE_PATCH_EXAMPLE,
        "</patch>",
        format_explanation,
        prompt,
    ]
    final_text = "\n".join(final_text)
    return final_text


def prompt_style_5_with_hints(instance):
    premise = "You will be provided with a partial code base and an issue from GitHub explaining a problem to resolve."
    readmes_text = make_code_text(instance["readmes"])
    code_text = make_code_text(instance["file_contents"])
    hints_text = instance['hints_text']
    instructions = (
        f"I need you to solve this issue by generating a specialized patch file that I can apply "
        + f"directly to this repository using git apply. Please respond with a single patch "
        + f"file in the following format."
    )
    instructions = (
        f"I need you to solve this issue by generating a specially formatted patch file that I can process and apply "
        + f"directly to this repository. Your response should be a single patch file in the following format.\n"
        + f"Given the following files:"
    )
    post_instructions = f"You can edit them as follows:"
    format_explanation = (
        f"In the patch file format, you can specify the source and target file for the following changes using "
        + f"\nsource_file: <source_file_name>\ntarget_file: <target_file_name>\n"
        + f"@@ source_start: <source_start_line_number> specifies the beginning of a change in the source file.\n"
        + f"@@ --- specifies the end of a change in the source file.\n"
        + f"Lines can either be unchanged (prefixed with *), removed (prefixed with -), or added (prefixed with +).\n"
        + f"Unchanged or removed lines are specified simply by their line number.\n"
        + f"You can make multiple changes per file, and multiple files per patch file."
    )
    prompt = 'Respond below:'
    problem_statement = instance["problem_statement"]
    final_text = [
        premise,
        "<issue>",
        problem_statement,
        "</issue>",
        "<hints>",
        hints_text,
        "</hints>",
        "<code>",
        readmes_text,
        code_text,
        "</code>",
        instructions,
        "<example>",
        FILE_CONTENTS_EXAMPLE,
        "</example>",
        post_instructions,
        "<patch>",
        SIMPLE_PATCH_EXAMPLE,
        "</patch>",
        format_explanation,
        prompt,
    ]
    final_text = "\n".join(final_text)
    return final_text


def prompt_style_6(instance):
    premise = "You will be provided with a partial code base and an issue from GitHub explaining a problem to resolve."
    readmes_text = make_code_text(instance["readmes"])
    code_text = make_code_text(instance["file_contents"])
    instructions = (
        f"I need you to solve this issue by generating a specialized patch file that I can apply "
        + f"directly to this repository using git apply. Please respond with a single patch "
        + f"file in the following format."
    )
    instructions = (
        f"I need you to solve this issue by generating a specially formatted patch file that I can process and apply "
        + f"directly to this repository. Your response should be a single patch file in the following format.\n"
        + f"Given the following files:"
    )
    post_instructions = f"You can edit them as follows:"
    format_explanation = (
        f"In the patch file format, you can specify the source and target file for the following changes using "
        + f"\nsource_file: <source_file_name>\ntarget_file: <target_file_name>\n"
        + f"@@ source_start: <source_start_line_number> specifies the beginning of a change in the source file.\n"
        + f"@@ --- specifies the end of a change in the source file.\n"
        + f"Lines can either be unchanged (prefixed with *), removed (prefixed with -), or added (prefixed with +).\n"
        + f"You can make multiple changes per file, and multiple files per patch file."
    )
    prompt = 'Respond below:'
    problem_statement = instance["problem_statement"]
    final_text = [
        premise,
        "<issue>",
        problem_statement,
        "</issue>",
        "<code>",
        readmes_text,
        code_text,
        "</code>",
        instructions,
        "<example>",
        FILE_CONTENTS_EXAMPLE,
        "</example>",
        post_instructions,
        "<patch>",
        CONTEXT_PATCH_EXAMPLE,
        "</patch>",
        format_explanation,
        prompt,
    ]
    final_text = "\n".join(final_text)
    return final_text


def ingest_files(filenames):
    files_dict = dict()
    for filename in filenames:
        with open(filename) as f:
            content = f.read()
        files_dict[filename] = content
    return files_dict


PROMPT_FUNCTIONS = {
    # "style-2": prompt_style_2,
    # "style-3": prompt_style_3,
    # "full_file_gen": full_file_gen,
    # "style-2-edits-only": prompt_style_2_edits_only,
    "style-5": prompt_style_5,
    "style-5-with-hints": prompt_style_5_with_hints,
    "style-6": prompt_style_6,
}


def add_retrieval_results(input_instances, retrieval_dir, k, file_source):
    """
    Adds retrieval results to input_instances in-place
    """
    retrieval_results = dict()
    for instance_id, instance in tqdm(
        input_instances.items(),
        total=len(input_instances),
        desc="Adding retrieval results",
    ):
        retrieval_results_path = Path(
            retrieval_dir,
            instance["repo"].split("/")[-1] + "-task-instances.retrieval.jsonl",
        )
        assert (
            retrieval_results_path.exists()
        ), f"Retrieval results not found at {retrieval_results_path}"
        if retrieval_results_path not in retrieval_results:
            d = [json.loads(line) for line in open(retrieval_results_path)]
            d = {x["instance_id"]: x["hits"] for x in d}
            retrieval_results[retrieval_results_path.as_posix()] = d
        instance["hits"] = retrieval_results[retrieval_results_path.as_posix()][
            instance_id
        ][:k]


def get_oracle_filenames(instance):
    """
    Returns the filenames that are changed in the patch
    """
    source_files = {
        patch_file.source_file.split("a/", 1)[-1]
        for patch_file in unidiff.PatchSet(instance["patch"])
    }
    gold_docs = set()
    for source_file in source_files:
        gold_docs.add(source_file)
    return gold_docs


def add_text_inputs(
    input_instances,
    retrieval_dir,
    k,
    prompt_style,
    file_source,
    max_context_len=None,
    tokenizer_name=None,
    verbose=False,
):
    """Adds text inputs context for prediction in-place.

    Args:
    - input_instances: dictionary with unprocessed input instances.
    - retrieval_dir: if using retrieval method for file_contents, specify retrieval_dir to add retrieval results
    - k: if using retrieval, specifies the maximum number of files to included within context
    - prompt_style: specify the function to generate instructions and prompt provided an instance (from PROMPT_FUNCTIONS)
    - file_source: where to collect file_contents (e.g. oracle or bm25)
    - verbose: set ContextManager verbose to True
    """
    if max_context_len is not None:
        assert (
            tokenizer_name is not None
        ), "Must specify tokenizer_name if using max_context_len"
        tokenizer, tokenizer_func = TOKENIZER_FUNCS[tokenizer_name]
    input_instances_copy = deepcopy(input_instances)
    if file_source in {"bm25"}:
        add_retrieval_results(input_instances_copy, retrieval_dir, k, file_source)
    orig_dir = os.getcwd()
    with TemporaryDirectory(
        dir="/scratch" if os.path.exists("/scratch") else "/tmp"
    ) as root_dir:
        for instance_id, instance in tqdm(
            input_instances_copy.items(),
            total=len(input_instances_copy),
            desc="Adding text inputs",
        ):
            try:
                with AutoContextManager(
                    instance, root_dir, verbose=verbose
                ) as cm:
                    readmes = cm.get_readme_files()
                    instance["readmes"] = ingest_files(readmes)
                    if max_context_len is not None:
                        instance["file_contents"] = dict()
                        base_text_inputs = PROMPT_FUNCTIONS[prompt_style](instance)
                        base_text_input_length = len(
                            tokenizer_func(base_text_inputs, tokenizer)
                        )
                    if file_source in {"oracle"}:
                        instance["file_contents"] = ingest_files(
                            get_oracle_filenames(instance)
                        )
                    elif file_source in {"bm25"}:
                        instance["file_contents"] = ingest_files(
                            [x["docid"] for x in instance["hits"]]
                        )
                    elif file_source in {"all"}:
                        instance["file_contents"] = ingest_directory_contents(
                            cm.repo_path
                        )
                    elif file_source in {"none"}:
                        instance["file_contents"] = dict()
                    else:
                        raise ValueError(f"Invalid file source {file_source}")
                    if max_context_len is not None:
                        cur_input_len = base_text_input_length
                        include_files = list()
                        for filename in [x["docid"] for x in instance["hits"]]:
                            content = make_code_text(
                                {filename: instance["file_contents"][filename]}
                            )
                            if tokenizer_name in {"llama"}:
                                tokens = tokenizer_func("\n" + content, tokenizer)
                                idx = tokens.index(13)
                                assert (
                                    idx <= 2
                                ), "Expected newline token id (13) to be one of the first three tokens"
                                tokens = tokens[idx + 1 :]  # remove newline tokens
                            else:
                                tokens = tokenizer_func(content, tokenizer)
                            if cur_input_len + len(tokens) < max_context_len:
                                include_files.append(filename)
                                cur_input_len += len(tokens)
                        instance["file_contents"] = {
                            filename: instance["file_contents"][filename]
                            for filename in include_files
                        }
                    input_instances[instance_id]["text_inputs"] = PROMPT_FUNCTIONS[prompt_style](instance)
            except Exception as e:
                print(f"Failed on instance {instance_id}", e)
                traceback.print_exc()
                input_instances[instance_id]["text_inputs"] = None
            finally:
                # if AutoContextManager fails to exit properly future exits will return the wrong directory
                os.chdir(orig_dir)
    os.chdir(orig_dir)
