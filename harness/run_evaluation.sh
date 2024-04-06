#!/bin/bash
# python run_evaluation.py \
#     --predictions_path "<path to predictions (.json)>" \
#     --swe_bench_tasks "<path to `swe-bench.json`>" \
#     --log_dir "<path to folder>" \
#     --testbed "<path to folder>" \
#     --skip_existing \
#     --timeout 900 \
#     --verbose

# python run_evaluation.py --predictions_path=predictions/sweep-04-02__SWE-bench_unassisted__test.jsonl --log_dir=logs --swe_bench_tasks=test --testbed=testbed --num_processes=1 # i don't know if its swe-bench-test
# python run_evaluation.py --predictions_path=predictions/ground_truth__SWE-bench_unassisted__test.jsonl --log_dir=logs --swe_bench_tasks=test --testbed=testbed --num_processes=1 # i don't know if its swe-bench-test
python run_evaluation.py --predictions_path=predictions/ground_truth_subset__SWE-bench_unassisted__test.jsonl --log_dir=logs --swe_bench_tasks=test --testbed=testbed --num_processes=1 # i don't know if its swe-bench-test
