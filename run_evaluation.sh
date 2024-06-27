#!/bin/bash
python -m swebench.harness.run_evaluation --predictions_path gold --max_workers 12 --cache env --run_id gold_verify
