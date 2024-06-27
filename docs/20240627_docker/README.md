# Containerized Evaluation Harness
June 27, 2024

We’re releasing an update that improves the reliability of the SWE-bench evaluation harness using **containerized environments** based on Docker.

In the original setup, we hypothesized that `conda` environments would be enough to enforce reproducible evaluation.
In hindsight, it is underspecified.
This past April, we put out [Bug Report 4/5/2024](docs/reports/20240405_eval_bug/README.md), that among several upgrades, adds explicit versioning for packages.

However, SWE-bench evaluation remained sensitive to discrepancies originating from different platforms and user-specific configurations, leading to inconsistent results.
To eliminate these irregularities, our new harness provisions **per-sample Docker images with Python virtual environments** that have been rigorously tested.

In the new Docker harness, **99.78% (2289/2294) of SWE-bench** tasks and **100% (300/300) of SWE-bench Lite** tasks consistently resolve correctly with the ground truth solution. Furthermore, containers spawned from these images can be used as development environments for agents that run and develop solutions iteratively.

## Running Evaluation
The main entrypoint for the evaluation harness is the `swebench.harness.run_evaluation` module.

Run the following command to see the available arguments:
```bash
python -m swebench.harness.run_evaluation -h
```

This module runs docker containers for each evaluation instance in parallel.
In the process of running the evaluation, the harness will:
1. Build a base image that install basic dependencies for all instances
2. Build "environment" images that initialize the python environment for various configurations that are common to multiple instances (in total there are about 60 of these - or 100GB of images)
3. Build "instance" images that install the specific dependencies and source code for each instance

The harness will then run the evaluation script in each instance container, and collect the results.
After the evaluation is complete, the harness will clean up the containers and images depending on the `--cache_level` argument.

## Choosing the right `cache_level`
Since the harness builds images for each instance, it can be time-consuming to rebuild these images every time you run an evaluation.
We provide a `cache_level` argument to control how the harness caches images between runs.
By default, the harness `cache_level` is set to `env`, which means that the harness will store the base and environment images, but not the instance images.
In this setting, the base and environment images will be reused across runs, but take up about 100GB of disk space.
At the time of release, we require about 120GB of free disk space to run the harness with any `cache_level`.
For most users, this is the recommended setting providing a good balance between evaluation speed and disk space usage.

For users who want the fastest possible evaluation times, we recommend setting `cache_level` to `instance`.
In this setting, the harness will store images for all instances; making evaluation extremely fast.
However, all base, environment, and instance images will be stored, taking up about 2,000GB of disk space.
While this setting is the fastest, it is also extremely disk space intensive.

For users who want to minimize disk space usage, we recommend setting `cache_level` to `base` or `none`, which will remove all the instance and environment images after each run.
Note at this time, this setting still requires about 100GB of disk space to store the base and environment images when first building them.

## Choosing the right `max_workers`
The harness runs instances in parallel using the `max_workers` argument.
Since the harness uses the docker daemon to run instances, the number of workers should be chosen based on the resources available on your machine.
In general, we don't recommend using a very large number of workers, as this can slow down the evaluation process.
Regardless your CPU count, we recommend using fewer than 28 workers.

On a 16-core machine with `max_workers=12`, it should be possible to run evaluation on SWE-bench Lite in about 30 minutes when using the `env` cache level and under 15 minutes when using the `instance` cache level.

On an 8-core machine with `max_workers=6`, it should be possible to run evaluation on SWE-bench Lite in about 50 minutes when using the `env` cache level and about 15 minutes when using the `instance` cache level.

Using a much larger number of workers will likely slow down the evaluation process.

## Future Steps
We'd like to soon make the harness even more user-friendly by providing pre-built docker images that include verified starting points for each instance.

We're also hoping to better enable evaluation via orchestration tools like Kubernetes, which would allow users to run evaluations on larger clusters of machines.

We're providing experimental support for running evaluations on `arm64` machines, but this is still in the early stages of development.
Users may experience substantial speed degradation when running evaluations on `arm64` machines.

## Deliverables
* Please use `swebench>=2.0` for the latest version of the benchmark - the old version is now deprecated but can still be accessed using `swebench<2.0`.

## Acknowledgements
This work was done in collaboration with the Preparedness team at OpenAI (including Oliver Jaffe, Chan Jun Shern, James Aung, Giulio Starace, Dane Sherburn, and Neil Chowdhury).

We'd also like to thank Cognition Labs for providing [inspiration](https://github.com/CognitionAI/devin-swebench-results/tree/main) in the design of the evaluation harness.

✍️ Carlos & John