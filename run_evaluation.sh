#!/bin/bash
python swebench/harness/run_evaluation.py \
    --predictions_path preds_sbl.json \
    --max_workers 8 \
    --cache instance \
    --instance_ids astropy__astropy-7746 django__django-13447 django__django-16046 psf__requests-863 scikit-learn__scikit-learn-25638 sympy__sympy-16106 django__django-10914 django__django-13448 django__django-16139 pydata__xarray-3364 scikit-learn__scikit-learn-25747 sympy__sympy-16281
