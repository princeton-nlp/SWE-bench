#!/bin/bash

python get_tasks_pipeline.py \
    --repos 'scikit-learn/scikit-learn', 'pallets/flask' \
    --path_prs '<path to folder to save PRs to>' \
    --path_tasks '<path to folder to save tasks to>'