from criteria import (
    contains_git_commit_hash,
    contains_hyperlinks,
    contains_image,
    contains_issue_reference,
    contains_non_modified_files,
    contains_pytest_match_arg,
    leq_n_code_lines,
    leq_n_files,
    leq_n_hunks,
    leq_n_words,
)
from datasets import load_dataset, disable_caching
disable_caching()


def filter_problem_statement(instance):
    problem_statement = instance["problem_statement"]
    repo = instance["repo"]
    if leq_n_words(problem_statement, 40) or \
        contains_hyperlinks(problem_statement, repo) or \
        contains_issue_reference(problem_statement, repo) or \
        contains_git_commit_hash(problem_statement) or \
        contains_image(problem_statement):
        return False
    return True


def filter_patch(instance):
    patch_text = instance["patch"]
    if contains_non_modified_files(patch_text) or \
        not leq_n_files(patch_text, 1) or \
        not leq_n_hunks(patch_text, 3):
        return False
    return True


def filter_patch_test(instance):
    patch_text = instance["test_patch"]
    if contains_pytest_match_arg(patch_text) or \
        not leq_n_code_lines(patch_text, 20):
        return False
    return True


if __name__ == "__main__":
    # Load the dataset
    test = load_dataset("princeton-nlp/SWE-bench")['test']
    print(f"Original size: {len(test)}")

    # Filter the dataset
    filtered = test.filter(filter_problem_statement)
    print(f"➡️\tAfter filtering on problem statement: {len(filtered)}")
    filtered = filtered.filter(filter_patch)
    print(f"➡️\tAfter filtering on patch: {len(filtered)}")
    filtered = filtered.filter(filter_patch_test)
    print(f"➡️\tAfter filtering on test patch: {len(filtered)}")

    # Sort remaining dataset by instance_id's
    filtered = filtered.sort("instance_id")

    # Save the filtered dataset to disk
    filtered.save_to_disk("swe_bench_lite")

