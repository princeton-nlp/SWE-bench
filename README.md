<p align="center">
  <a href="http://swe-bench.github.io">
    <img src="docs/assets/figures/swellama_banner.svg" style="height: 10em" alt="Kawi the SWE-Llama" />
  </a>
</p>

<p align="center"><strong>[&nbsp;<a href="https://swebench.com/SWE-bench/">Read the Docs</a>&nbsp;]</strong></p>

<p align="center">
  <a href="docs/other_languages/README_JP.md">日本語</a> |
  <a href="docs/other_languages/README_CN.md">中文简体</a> |
  <a href="docs/other_languages/README_TW.md">中文繁體</a>
</p>

<p align="center">
    <a href="https://www.python.org/">
        <img alt="Build" src="https://img.shields.io/badge/Python-3.8+-1f425f.svg?color=purple">
    </a>
    <a href="https://copyright.princeton.edu/policy">
        <img alt="License" src="https://img.shields.io/badge/License-MIT-blue">
    </a>
    <a href="https://badge.fury.io/py/swebench">
        <img src="https://badge.fury.io/py/swebench.svg">
    </a>
</p>

---

Code and data for the following works:
* [ICLR 2025] <a href="https://arxiv.org/abs/2410.03859">SWE-bench Multimodal: Do AI Systems Generalize to Visual Software Domains?</a>
* [ICLR 2024 Oral] <a href="https://arxiv.org/abs/2310.06770">SWE-bench: Can Language Models Resolve Real-World GitHub Issues?</a>

## 📰 News
* **[Sep. 1, 2026]**: SWE-bench Multimodal v2 is now fully open source, with 480 tasks available for local evaluation! See the [website](https://swebench.com/multimodal) and [dataset](https://huggingface.co/datasets/SWE-bench/SWE-bench_Multimodal) to get started.
* **[Jan. 13, 2025]**: We've integrated [SWE-bench Multimodal](https://swebench.com/multimodal) ([paper](https://arxiv.org/abs/2410.03859), [dataset](https://huggingface.co/datasets/SWE-bench/SWE-bench_Multimodal)) into this repository!
* **[Jan. 13, 2025]**: We've released [sb-cli](https://github.com/swe-bench/sb-cli), our cloud-based evaluation tool for submitting runs to the SWE-bench leaderboards.
* **[Jan. 11, 2025]**: Thanks to [Modal](https://modal.com/), you can now run evaluations entirely on the cloud! See [here](https://github.com/swe-bench/SWE-bench/blob/main/docs/assets/evaluation.md#%EF%B8%8F-evaluation-with-modal) for more details.
* **[Aug. 13, 2024]**: Introducing *SWE-bench Verified*! Part 2 of our collaboration with [OpenAI Preparedness](https://openai.com/preparedness/). A subset of 500 problems that real software engineers have confirmed are solvable. Check out more in the [report](https://openai.com/index/introducing-swe-bench-verified/)!
* **[Jun. 27, 2024]**: We have an exciting update for SWE-bench - with support from [OpenAI's Preparedness](https://openai.com/preparedness/) team: We're moving to a fully containerized evaluation harness using Docker for more reproducible evaluations! Read more in our [report](https://github.com/swe-bench/SWE-bench/blob/main/docs/20240627_docker/README.md).
* **[Apr. 2, 2024]**: We have released [SWE-agent](https://github.com/SWE-agent/SWE-agent), which sets the state-of-the-art on the full SWE-bench test set! ([Tweet 🔗](https://twitter.com/jyangballin/status/1775114444370051582))
* **[Jan. 16, 2024]**: SWE-bench has been accepted to ICLR 2024 as an oral presentation! ([OpenReview 🔗](https://openreview.net/forum?id=VTF8yNQM66))

## 👋 Overview
SWE-bench is a benchmark for evaluating large language models on real world software issues collected from GitHub.
Given a *codebase* and an *issue*, a language model is tasked with generating a *patch* that resolves the described problem.

<img src="docs/assets/figures/teaser.png">

To access SWE-bench, copy and run the following code:
```python
from datasets import load_dataset
swebench = load_dataset('princeton-nlp/SWE-bench', split='test')
```

## 🚀 Set Up
SWE-bench uses Docker for reproducible evaluations.
Follow the instructions in the [Docker setup guide](https://docs.docker.com/engine/install/) to install Docker on your machine.
If you're setting up on Linux, we recommend seeing the [post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/) as well.

Finally, to build SWE-bench from source, follow these steps:
```bash
git clone git@github.com:SWE-bench/SWE-bench.git
cd SWE-bench
pip install -e .

# Required for local image builds with the v5 CLI. This path is only an example.
git clone --depth 1 https://github.com/SWE-bench/swe-bench-tasks.git ./swe-bench-tasks
swebench dataset check ./swe-bench-tasks
```
You can replace this path with any local checkout location.

Test your installation by running:
```bash
swebench eval verified --gold \
    -i sympy__sympy-20590 \
    --run-id validate-gold \
    --task-repo ./swe-bench-tasks
```
> [!NOTE]
> The current v5 CLI builds images from a task repo. On an M-series Mac or another ARM-based system, use `--task-repo` so the images are built locally with Docker Buildx.

## 💽 Usage
Evaluate patch predictions with the following command:
```bash
swebench eval verified -p <path_to_predictions> --run-id <run_id> -j <num_workers>
```

`DATASET` accepts an alias (`full`, `verified`, `multimodal`, `multilingual`), a
HuggingFace id, or a local path. Anything else is passed through as given, so
`SWE-bench/SWE-bench_Lite` works too:

```bash
swebench eval verified --gold                 # reference patches
swebench eval multimodal --gold -i carbon-design-system__carbon-10188
swebench report <run_id> -d verified          # re-grade saved logs, no containers
```

Other commands:

```bash
swebench infer verified -m gpt-5 -o preds -w 8        # generate predictions with mini-SWE-agent
swebench images build verified -j 8           # build/pull images ahead of time
swebench images check multilingual            # verify images exist on the registry
swebench images clean --run-id <run_id>       # remove leftover containers
swebench submit hf <run_id> -b <user/bucket>      # publish results to an HF bucket
swebench --help                               # all commands
```

> [!NOTE]
> The previous `python -m swebench.harness.run_evaluation ...` form still works
> and takes the same arguments as before.

This command will generate docker build logs (`logs/build_images`) and evaluation logs
(`logs/evaluation`) in the current directory.

The run summary is written to `logs/evaluation/<run_id>/results.json`.

> [!NOTE]
> **Result Caching**: The evaluation harness caches results by `run_id` and `instance_id` only. If you run the same instance with the same `run_id` multiple times, even with different prediction diffs, the harness will reuse the cached results from the first run and will not re-evaluate. To re-evaluate an instance with a different prediction diff, you must use a different `run_id`.

> [!WARNING]
> SWE-bench evaluation can be resource intensive
> We recommend running on an `x86_64` machine with at least 120GB of free storage, 16GB of RAM, and 8 CPU cores.
> We recommend using fewer than `min(0.75 * os.cpu_count(), 24)` for `--max_workers`.
>
> If running with Docker desktop, make sure to increase your virtual disk space to ~120 free GB. Set max_workers to be consistent with the above for the CPUs available to Docker.
>
> Support for `arm64` machines is experimental.

To see the full list of arguments for the evaluation harness, run:
```bash
swebench eval --help
```

See the [evaluation tutorial](docs/guides/evaluation.md) for the full rundown on datasets you can evaluate.
If you're looking for non-local, cloud based evaluations, check out...
* [sb-cli](https://github.com/swe-bench/sb-cli), our tool for running evaluations automatically on AWS, or...
* Running SWE-bench evaluation on [Modal](https://modal.com/). Details [here](docs/guides/evaluation.md#Cloud-Based-Evaluation)

Additionally, you can also:
* [Train](https://github.com/swe-bench/SWE-bench/tree/main/swebench/inference/make_datasets) your own models on our pre-processed datasets. (🆕 Check out [SWE-smith](https://swesmith.com/), a dedicated toolkit for creating SWE training data.)
* Run [inference](docs/reference/inference.md) on existing models (both local and API models). The inference step is where you give the model a repo + issue and have it generate a fix.
*  Run SWE-bench's [data collection procedure](https://github.com/swe-bench/SWE-bench/blob/main/swebench/collect/) ([tutorial](docs/assets/collection.md)) on your own repositories, to make new SWE-Bench tasks.
    * ⚠️ We are temporarily pausing support for queries around creating SWE-bench instances. Please see the note in the tutorial.

## ⬇️ Downloads
| Datasets | Models | RAG |
| - | - | - |
| [💿 SWE-bench](https://huggingface.co/datasets/SWE-bench/SWE-bench) | [🦙 SWE-Llama 13b](https://huggingface.co/princeton-nlp/SWE-Llama-13b) | [🤗 "Oracle" Retrieval](https://huggingface.co/datasets/princeton-nlp/SWE-bench_oracle) |
| [💿 SWE-bench Lite](https://huggingface.co/datasets/SWE-bench/SWE-bench_Lite) | [🦙 SWE-Llama 13b (PEFT)](https://huggingface.co/princeton-nlp/SWE-Llama-13b-peft) | [🤗 BM25 Retrieval 13K](https://huggingface.co/datasets/princeton-nlp/SWE-bench_bm25_13K) |
| [💿 SWE-bench Verified](https://huggingface.co/datasets/SWE-bench/SWE-bench_Verified) | [🦙 SWE-Llama 7b](https://huggingface.co/princeton-nlp/SWE-Llama-7b) | [🤗 BM25 Retrieval 27K](https://huggingface.co/datasets/princeton-nlp/SWE-bench_bm25_27K) |
| [💿 SWE-bench Multimodal](https://huggingface.co/datasets/SWE-bench/SWE-bench_Multimodal) | [🦙 SWE-Llama 7b (PEFT)](https://huggingface.co/princeton-nlp/SWE-Llama-7b-peft) | [🤗 BM25 Retrieval 40K](https://huggingface.co/datasets/princeton-nlp/SWE-bench_bm25_40K) |
| | | [🤗 BM25 Retrieval 50K (Llama tokens)](https://huggingface.co/datasets/princeton-nlp/SWE-bench_bm25_50k_llama) |

## 💫 Contributions
We would love to hear from the broader NLP, Machine Learning, and Software Engineering research communities, and we welcome any contributions, pull requests, or issues!
To do so, please either file a new pull request or issue and fill in the corresponding templates accordingly. We'll be sure to follow up shortly!

Contact person: [Carlos E. Jimenez](http://www.carlosejimenez.com/) and [John Yang](https://john-b-yang.github.io/) (Email: carlosej@princeton.edu, johnby@stanford.edu).

## ✍️ Citation & license
MIT license. Check `LICENSE.md`.

If you find our work helpful, please use the following citations.

For SWE-bench (Verified):
```bibtex
@inproceedings{
    jimenez2024swebench,
    title={{SWE}-bench: Can Language Models Resolve Real-world Github Issues?},
    author={Carlos E Jimenez and John Yang and Alexander Wettig and Shunyu Yao and Kexin Pei and Ofir Press and Karthik R Narasimhan},
    booktitle={The Twelfth International Conference on Learning Representations},
    year={2024},
    url={https://openreview.net/forum?id=VTF8yNQM66}
}
```

For SWE-bench Multimodal
```bibtex
@inproceedings{
    yang2024swebenchmultimodal,
    title={{SWE}-bench Multimodal: Do AI Systems Generalize to Visual Software Domains?},
    author={John Yang and Carlos E. Jimenez and Alex L. Zhang and Kilian Lieret and Joyce Yang and Xindi Wu and Ori Press and Niklas Muennighoff and Gabriel Synnaeve and Karthik R. Narasimhan and Diyi Yang and Sida I. Wang and Ofir Press},
    booktitle={The Thirteenth International Conference on Learning Representations},
    year={2025},
    url={https://openreview.net/forum?id=riTiq3i21b}
}
```

For SWE-bench Multilingual
```bibtex
@misc{yang2025swesmith,
    title={SWE-smith: Scaling Data for Software Engineering Agents},
    author={John Yang and Kilian Lieret and Carlos E. Jimenez and Alexander Wettig and Kabir Khandpur and Yanzhe Zhang and Binyuan Hui and Ofir Press and Ludwig Schmidt and Diyi Yang},
    year={2025},
    eprint={2504.21798},
    archivePrefix={arXiv},
    primaryClass={cs.SE},
    url={https://arxiv.org/abs/2504.21798},
}
```

## Our Other Projects

<div align="center">
  <a href="https://github.com/SWE-bench/sb-cli"><img src="https://raw.githubusercontent.com/SWE-agent/swe-agent-media/refs/heads/main/media/logos_banners/sbcli_logo_text_below.svg" alt="sb-cli" height="120px"></a>
   &nbsp;&nbsp;
  <a href="https://github.com/SWE-bench/SWE-smith"><img src="https://raw.githubusercontent.com/SWE-agent/swe-agent-media/refs/heads/main/media/logos_banners/swesmith_logo_text_below.svg" alt="SWE-smith" height="120px"></a>
   &nbsp;&nbsp;
  <a href="https://github.com/SWE-agent/SWE-agent"><img src="https://raw.githubusercontent.com/SWE-agent/swe-agent-media/refs/heads/main/media/logos_banners/sweagent_logo_text_below.svg" alt="SWE-agent" height="120px"></a>
   &nbsp;&nbsp;
  <a href="https://github.com/codeclash-ai/codeclash"><img src="https://raw.githubusercontent.com/SWE-agent/swe-agent-media/refs/heads/main/media/logos_banners/codeclash_logo_text_below.svg" alt="CodeClash" height="120px"></a>
  &nbsp;&nbsp;
  <a href="https://github.com/SWE-agent/Mini-SWE-Agent"><img src="https://raw.githubusercontent.com/SWE-agent/swe-agent-media/refs/heads/main/media/logos_banners/mini_logo_text_below.svg" alt="Mini-SWE-Agent" height="120px"></a>
  &nbsp;&nbsp;
  <a href="https://github.com/SWE-agent/SWE-ReX"><img src="https://raw.githubusercontent.com/SWE-agent/swe-agent-media/refs/heads/main/media/logos_banners/swerex_logo_text_below.svg" alt="SWE-ReX" height="120px"></a>
</div>
