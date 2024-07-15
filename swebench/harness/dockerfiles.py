# IF you change the base image, you need to rebuild all images (run with --force_rebuild)
_DOCKERFILE_BASE = r"""
FROM --platform={platform} ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt update && apt install -y \
wget \
git \
build-essential \
libffi-dev \
libtiff-dev \
python3 \
python3-pip \
python-is-python3 \
jq \
curl \
locales \
locales-all \
tzdata \
&& rm -rf /var/lib/apt/lists/*

# Download and install conda
RUN wget 'https://repo.anaconda.com/miniconda/Miniconda3-py311_23.11.0-2-Linux-{conda_arch}.sh' -O miniconda.sh \
    && bash miniconda.sh -b -p /opt/miniconda3
# Add conda to PATH
ENV PATH=/opt/miniconda3/bin:$PATH
# Add conda to shell startup scripts like .bashrc (DO NOT REMOVE THIS)
RUN conda init --all
RUN conda config --append channels conda-forge

RUN adduser --disabled-password --gecos 'dog' nonroot
"""

_DOCKERFILE_ENV = r"""FROM --platform={platform} sweb.base.{arch}:latest

COPY ./setup_env.sh /root/
RUN chmod +x /root/setup_env.sh
RUN /bin/bash -c "source ~/.bashrc && /root/setup_env.sh"

WORKDIR /testbed/

# Automatically activate the testbed environment
RUN echo "source /opt/miniconda3/etc/profile.d/conda.sh && conda activate testbed" > /root/.bashrc
"""

_DOCKERFILE_INSTANCE = r"""FROM --platform={platform} {env_image_name}

COPY ./setup_repo.sh /root/
RUN /bin/bash /root/setup_repo.sh

WORKDIR /testbed/
"""


def get_dockerfile_base(platform, arch):
    if arch == "arm64":
        conda_arch = "aarch64"
    else:
        conda_arch = arch
    return _DOCKERFILE_BASE.format(platform=platform, conda_arch=conda_arch)


def get_dockerfile_env(platform, arch):
    return _DOCKERFILE_ENV.format(platform=platform, arch=arch)


def get_dockerfile_instance(platform, env_image_name):
    return _DOCKERFILE_INSTANCE.format(platform=platform, env_image_name=env_image_name)
