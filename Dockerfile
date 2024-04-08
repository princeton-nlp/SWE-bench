FROM ubuntu:22.04

RUN apt update && apt install -y git wget bash gcc git jq wget libffi-dev

WORKDIR /root
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
RUN bash ./Miniconda3-latest-Linux-x86_64.sh -b -p /root/miniconda3
ENV PATH="/root/miniconda3/bin:${PATH}"
RUN conda init

WORKDIR /opt
RUN git clone https://github.com/yuntongzhang/SWE-bench.git

WORKDIR SWE-bench
RUN conda env create -f environment.yml
RUN ln -sf /bin/bash /bin/sh

ENV DEBIAN_FRONTEND=noninteractive
RUN apt install -y libffi-dev python3-pytest libfreetype6-dev libqhull-dev
RUN apt install -y pkg-config texlive cm-super dvipng python-tk ffmpeg
RUN apt install -y imagemagick fontconfig
RUN apt install -y ghostscript inkscape graphviz
RUN apt install -y optipng fonts-comic-neue  python3-pikepdf

RUN echo ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true | debconf-set-selections
RUN apt install -y ttf-mscorefonts-installer

RUN apt install -y build-essential libssl-dev

ENTRYPOINT [ "/bin/bash" ]
