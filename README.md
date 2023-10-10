<p align="center">
  <a href="https://github.com/princeton-nlp/Llamao">
    <img src="assets/swellama_banner.svg" width="50%" alt="swellama logo" />
  </a>
</p>

---
<p align="center">
Companion repository containing the code and data for our paper "<a href="http://swe-bench.github.io/paper.pdf">SWE-bench: Can Language Models Resolve Real-World GitHub Issues?</a>".
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
You can download the SWE-bench dataset from [source](https://drive.google.com/uc?export=download&id=164g55i3_B78F6EphCZGtgSrd2GneFyRM) (`.json` file) or from [HuggingFace](https://huggingface.co/datasets/princeton-nlp/SWE-bench)

Find out more about how to use SWE-bench, such as how to...
* [Evaluate](https://github.com/princeton-nlp/SWE-bench/blob/master/harness/README.md) models against SWE-bench
* Run SWE-bench's [data collection procedure](https://github.com/princeton-nlp/SWE-bench/blob/master/collect/README.md) on your own repositories
* Get model generations with our [inference pipeline](https://github.com/princeton-nlp/SWE-bench/blob/master/inference/) and SWE-Llama [13B](https://huggingface.co/princeton-nlp/SWE-Llama-13b) and [7B](https://huggingface.co/princeton-nlp/SWE-Llama-7b) (Parameter Efficient Alternatives: [13B](https://huggingface.co/princeton-nlp/SWE-Llama-13b-peft) and [7B](https://huggingface.co/princeton-nlp/SWE-Llama-7b-peft)).

## 💫 Contributions
We would love to hear from the broader NLP, Machine Learning, and Software Engineering research communities, and we welcome any contributions, pull requests, or issues!
To do so, please either file a new pull request or issue and fill in the corresponding templates accordingly. We'll be sure to follow up shortly!

Contact person: [Carlos E. Jimenez](http://www.carlosejimenez.com/) and [John Yang](https://john-b-yang.github.io/) (Email: {carlosej, jy1682}@princeton.edu).

## ✍️ Citation
If you find our work helpful, please use the following citations.
```
@inproceedings{jimenez2023swebench,
  title = {SWE-bench: Can Language Models Resolve Real-World GitHub Issues?},
  author = {Jimenez, Carlos E. and Yang, John and Wettig, Alexander and Yao, Shunyu and Pei, Kexin and Press, Ofir and Narasimhan, Karthik},
  booktitle = {ArXiv},
  year = {2023},
}
```

## 🪪 License
MIT. Check `LICENSE.md`.
