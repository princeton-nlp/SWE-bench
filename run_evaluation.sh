#!/bin/bash
python swebench/harness/run_evaluation.py \
    --predictions_path preds_sbl.json \
    --max_workers 8 \
    --cache instance
