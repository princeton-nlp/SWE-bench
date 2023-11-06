<p align="center">
  <a href="https://github.com/princeton-nlp/Llamao">
    <img src="assets/swellama_banner.png" width="50%" alt="Kawi the SWE-Llama" />
  </a>
</p>

---
<p align="center">
Code and data for paper "<a href="http://swe-bench.github.io/paper.pdf">SWE-bench: Can Language Models Resolve Real-World GitHub Issues?</a>".
    </br>
    </br>
    <a href="https://www.python.org/">
        <img alt="Build" src="https://img.shields.io/badge/Python-3.8+-1f425f.svg?color=purple">
    </a>
    <a href="https://copyright.princeton.edu/policy">
        <img alt="License" src="https://img.shields.io/badge/License-MIT-blue">
    </a>
</p>

Please refer our [website](http://swe-bench.github.io) for the public leaderboard and the [change log](https://github.com/princeton-nlp/SWE-bench/blob/master/CHANGELOG.md) for information on the latest updates to the SWE-bench benchmark.

## 👋 Overview
SWE-bench is a benchmark for evaluating large language models on real world software issues collected from GitHub.
Given a *codebase* and an *issue*, a language model is tasked with generating a *patch* that resolves the described problem.

<img src="assets/teaser.png">

## 🚀 Set Up
To build SWE-bench from source, follow these steps:
1. Clone this repository locally
2. `cd` into the repository.
3. Run `conda env create -f environment.yml` to created a conda environment named `swe-bench`
4. Activate the environment with `conda activate swe-bench`

## 💽 Usage
You can download the SWE-bench dataset directly ([dev](https://drive.google.com/uc?export=download&id=1M9lkzJDZwWXwRxRp_7P7XbFP8tqhvUl0), [test](https://drive.google.com/uc?export=download&id=164g55i3_B78F6EphCZGtgSrd2GneFyRM) sets) or from [HuggingFace](https://huggingface.co/datasets/princeton-nlp/SWE-bench)

Find out more about how to use SWE-bench, such as how to...
* [Evaluate](https://github.com/princeton-nlp/SWE-bench/blob/master/harness/) models against SWE-bench
* Run SWE-bench's [data collection procedure](https://github.com/princeton-nlp/SWE-bench/blob/master/collect/) on your own repositories
* Train your own models on our pre-tokenized datasets or run [inference](https://github.com/princeton-nlp/SWE-bench/blob/master/inference/) on models directly.

| Datasets | Models |
| - | - |
| [🤗 SWE-bench](https://huggingface.co/datasets/princeton-nlp/SWE-bench) | [🦙 SWE-Llama 13b](https://huggingface.co/princeton-nlp/SWE-Llama-13b) |
| [🤗 "Oracle" Retrieval (Llama tokenized)](https://huggingface.co/datasets/princeton-nlp/SWE-bench_oracle_llama) | [🦙 SWE-Llama 13b (PEFT)](https://huggingface.co/princeton-nlp/SWE-Llama-13b-peft) |
| [🤗 "Oracle" Retrieval (cl100k tokenized)](https://huggingface.co/datasets/princeton-nlp/SWE-bench_oracle_cl100k) | [🦙 SWE-Llama 7b](https://huggingface.co/princeton-nlp/SWE-Llama-7b) |
| [🤗 BM25 Retrieval 13k (cl100k tokenized)](https://huggingface.co/datasets/princeton-nlp/SWE-bench_bm25_13k_cl100k) | [🦙 SWE-Llama 7b (PEFT)](https://huggingface.co/princeton-nlp/SWE-Llama-7b-peft) |
| [🤗 BM25 Retrieval 27k (cl100k tokenized)](https://huggingface.co/datasets/princeton-nlp/SWE-bench_bm25_27k_cl100k) | |
| [🤗 BM25 Retrieval 50k (Llama tokenized)](https://huggingface.co/datasets/princeton-nlp/SWE-bench_bm25_50k_llama)   | |

## 🍎 Tutorials
We've also written the following blog posts on how to use different parts of SWE-bench.
If you'd like to see a post about a particular topic, please let us know via an issue.
* [Nov 1. 2023] Collecting Evaluation Tasks for SWE-Bench ([🔗](https://github.com/princeton-nlp/SWE-bench/tree/main/tutorials/collection.md))
* [Nov 6. 2023] Evaluating on SWE-bench ([🔗](https://github.com/princeton-nlp/SWE-bench/tree/main/tutorials/evaluation.md))

## 💫 Contributions
We would love to hear from the broader NLP, Machine Learning, and Software Engineering research communities, and we welcome any contributions, pull requests, or issues!
To do so, please either file a new pull request or issue and fill in the corresponding templates accordingly. We'll be sure to follow up shortly!

Contact person: [Carlos E. Jimenez](http://www.carlosejimenez.com/) and [John Yang](https://john-b-yang.github.io/) (Email: {carlosej, jy1682}@princeton.edu).

## ✍️ Citation
If you find our work helpful, please use the following citations.
```
@misc{jimenez2023swebench,
      title={SWE-bench: Can Language Models Resolve Real-World GitHub Issues?}, 
      author={Carlos E. Jimenez and John Yang and Alexander Wettig and Shunyu Yao and Kexin Pei and Ofir Press and Karthik Narasimhan},
      year={2023},
      eprint={2310.06770},
      archivePrefix={arXiv},
      primaryClass={cs.CL}
}
```

## 🪪 License
MIT. Check `LICENSE.md`.
