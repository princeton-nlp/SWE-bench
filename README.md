# Fork of SWE-bench

Fork of [SWE-bench](https://github.com/princeton-nlp/SWE-bench) with modifications to use some of its scripts.

## Docker images

```
# only evaluation environment
yuntongzhang/swe-bench:latest
# additionally with projects setup for other tools
yuntongzhang/swe-bench:experiment
```

## Instructions

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
ln -sf /bin/bash /bin/sh
```

Also install system level packages required by the benchmark subjects:
These are important for successfully installing the benchmark subject dependencies, as well as
successfully running the benchmark subject tests.

```
sudo apt install -y libffi-dev python3-pytest libfreetype6-dev libqhull-dev pkg-config texlive cm-super dvipng python-tk ffmpeg imagemagick fontconfig ghostscript inkscape graphviz optipng fonts-comic-neue python3-pikepdf build-essential libssl-dev

sudo apt install ttf-mscorefonts-installer
```

### To set up task instances for other tools

Sometimes you may want to only set up the projects' environments without running any evaluation.
This is useful if you want to inspect the particular project states.

**To set up all task instances, do:**

```
python harness/run_setup.py --log_dir logs --testbed testbed --result_dir setup_result
```

**You can also use multiple processes for setting up environment. However, note that conda is not thread-safe, and doing this may result in deadlock:**

```
python harness/run_setup.py --log_dir logs --testbed testbed --result_dir setup_result --num_processes 16
```

**If you only want to set up a subset of tasks, write the list of tasks into a file <subset_file> and do:**

```
python harness/run_setup.py --log_dir logs --testbed testbed --result_dir setup_result --subset_file <subset_file> --num_processes 16
```

**If you only want to write out the setup json files without actually cloning the repos and perform the actual setup, do:**

```
python harness/run_setup.py --log_dir logs --testbed testbed --result_dir setup_result --only_dump_files
```

### To evaluate on some task instances

1. Prepare a prediction file in json. This `prediction.json` file should contain the model's output
   in the field 'model_patch', which will be used for evaluation.
   If just want to evaluate on one instance, you can put only that entry's answer in this file.
2. Prepare the big json file `swe-bench.json` that contains all the task instance definitions.
   This can be downloaded from the original Github repo.
3. Create directories `logs` and `eval-testbed` for storing logs and the temporarily cloned projects.

Run the evaluation script like this:

NOTE: do not overwrite existing `testbed` directory, as it contains setup for other tools to run.

```
mkdir eval_logs
mkdir eval_testbed
python harness/run_evaluation.py --predictions_path ../predictions_for_swebench.json --swe_bench_tasks ./data/swe-bench.json --log_dir eval_logs --testbed eval_testbed  --verbose
```
