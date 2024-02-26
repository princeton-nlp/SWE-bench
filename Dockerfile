FROM continuumio/miniconda3:latest

RUN apt-get update && \
    apt-get install -y bash gcc git jq wget libffi-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN git config --global user.email "swebench@pnlp.org"
RUN git config --global user.name "swebench"

RUN conda --version

COPY . /root/SWE-bench

WORKDIR /root/SWE-bench
RUN conda env create -f environment.yml

CMD ["/bin/bash"]
