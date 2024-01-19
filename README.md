# Fork of SWE-bench

Fork of [SWE-bench](https://github.com/princeton-nlp/SWE-bench) with modifications to use some of its scripts.


## Instructions

_Before everything, install SWE-bench and conda activate._


### To install

First, install miniconda:

```
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
```

Create and activate conda environment for the benchmark:

```
conda env create -f environment.yml
conda activate swe-bench
```

In some distro, `/bin/sh` points to dash instead of bash, which can cause issues when `source` is used in the benchmark code. To change it to bash:

```
sudo dpkg-reconfigure dash
```

Also install system level packages required by the benchmark subjects:

```
sudo apt install libffi-dev
```


### To evaluate on some task instances

- Prepare a prediction file in json. This `prediction.json` file should contain the model's output
in the field 'model_patch', which will be used for evaluation.
If just want to evaluate on one instance, you can put only that entry's answer in this file.
- Prepare the big json file `swe-bench.json` that contains all the task instance definitions.
This can be downloaded from the original Github repo.
- Create directories `logs` and `clone` for storing logs and the temporarily cloned projects.
- Run the script like this:

```
python harness/run_evaluation.py --predictions_path ../astropy-6938-prediction.json --swe_bench_tasks ./data/swe-bench.json --log_dir ../logs --testbed ../clone --conda_path  ~/miniconda3 --timeout 900 --verbose
```

### To only setup projects for some instances

Sometimes you may want to only set up the projects' environments without running any evaluation.
This is useful if you want to inspect the particular project states.

To set up all task instances, do:

```
python harness/run_setup.py --log_dir logs --swe_bench_tasks ./data/swe-bench.json --testbed testbed --result_dir setup_result
```

You can also use multiple processes for setting up environment. However, note that conda is not
thread-safe, and doing this may result in deadlock:

```
python harness/run_setup.py --log_dir logs --swe_bench_tasks ./data/swe-bench.json --testbed testbed --result_dir setup_result --num_processes 16
```

If you only want to set up a subset of tasks, write the list of tasks into a file <subset_file> and do:

```
python harness/run_setup.py --log_dir logs --swe_bench_tasks ./data/swe-bench.json --testbed testbed --result_dir setup_result --subset_file <subset_file> --num_processes 16
```
