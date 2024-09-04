#!/bin/bash

# IMPORTANT: we should rerun this on the original swe-bench mirrors, with the original timeline,
# to check that our results are close to the original.

# Chris: we needed to add a new pattern to get_versions.py to handle the way flask's version
# is specified now, in pyproject.toml.
#
python swebench/versioning/get_versions.py \
    --instances_path swebench/collect/Q3/flask-task-instances.jsonl \
    --retrieval_method build \
    --conda_env sweagent \
    --path_conda /Users/vin/miniconda3/ \
    --num_workers 1 \
    --output_dir swebench/collect/Q3_versioned/ \
    --testbed ./testbed

# Chris: this seems to be broken for now—matplotlib won't build pybind11 under conda. We should
# investigate this, but I'm moving on for now.
#
(cd swebench/versioning/extract_web && python get_versions_matplotlib.py)

# Chris: this must be github (at least, or 'mix') because the grep for the version would never
# have returned the types of values they expected. Take a look at the history of __init__.py in
# django/
#
python swebench/versioning/get_versions.py \
    --instances_path swebench/collect/Q3/django-task-instances.jsonl \
    --retrieval_method github \
    --conda_env sweagent \
    --path_conda /Users/vin/miniconda3/ \
    --num_workers 1 \
    --output_dir swebench/collect/Q3_versioned/ \
    --testbed ./testbed

# Chris: this one was a pain. Had to manually modify get_versions_astropy.py in ways that made it clear
# they hadn't actually tested it.
#
(cd swebench/versioning/extract_web && python get_versions_astropy.py)

# Chris: this one worked as-is, without a hitch. :)
#
python swebench/versioning/get_versions.py \
    --instances_path swebench/collect/Q3/pytest-task-instances.jsonl \
    --retrieval_method build \
    --conda_env sweagent \
    --path_conda /Users/vin/miniconda3/ \
    --num_workers 1 \
    --output_dir swebench/collect/Q3_versioned/ \
    --testbed ./testbed

# Chris: I used github here because this one lists a version path in constants, but
# not a build command.
#
python swebench/versioning/get_versions.py \
    --instances_path swebench/collect/Q3/pylint-task-instances.jsonl \
    --retrieval_method github \
    --conda_env sweagent \
    --path_conda /Users/vin/miniconda3/ \
    --num_workers 1 \
    --output_dir swebench/collect/Q3_versioned/ \
    --testbed ./testbed

# Chris: requests pulled 0 instances marked tests. So there is nothing to version.
# # python swebench/versioning/get_versions.py \
# #     --instances_path swebench/collect/Q3/requests-task-instances.jsonl \
# #     --retrieval_method github \
# #     --conda_env sweagent \
# #     --path_conda /Users/vin/miniconda3/ \
# #     --num_workers 1 \
# #     --output_dir swebench/collect/Q3_versioned/ \
# #     --testbed ./testbed

# Chris: also worked as-is.
#
python swebench/versioning/get_versions.py \
    --instances_path swebench/collect/Q3/scikit-learn-task-instances.jsonl \
    --retrieval_method github \
    --conda_env sweagent \
    --path_conda /Users/vin/miniconda3/ \
    --num_workers 1 \
    --output_dir swebench/collect/Q3_versioned/ \
    --testbed ./testbed

# Chris: this one proved to be empty. No task instances were found.
#
# # python swebench/versioning/get_versions.py \
# #     --instances_path swebench/collect/Q3/seaborn-task-instances.jsonl \
# #     --retrieval_method github \
# #     --conda_env sweagent \
# #     --path_conda /Users/vin/miniconda3/ \
# #     --num_workers 1 \
# #     --output_dir swebench/collect/Q3_versioned/ \
# #     --testbed ./testbed

# Chris: seems to have worked out of the box.
#
python swebench/versioning/get_versions.py \
    --instances_path swebench/collect/Q3/sympy-task-instances.jsonl \
    --retrieval_method github \
    --conda_env sweagent \
    --path_conda /Users/vin/miniconda3/ \
    --num_workers 1 \
    --output_dir swebench/collect/Q3_versioned/ \
    --testbed ./testbed

# Chris: this one worked with the same tweak to get_versions.py that we made for flask.
#
(cd swebench/versioning/extract_web && python get_versions_xarray.py)