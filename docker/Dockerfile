FROM nvidia/cuda:11.1-devel-ubuntu18.04

ARG WORK_DIR="/work"

ENV DEBIAN_FRONTEND=noninteractive

SHELL ["/bin/bash", "-c"]

RUN sed -i 's@archive.ubuntu.com@jp.archive.ubuntu.com@g' /etc/apt/sources.list

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    wget \
    unzip \
    git \
    rsync \
    libjpeg-dev \
    dh-autoreconf \
    gcc-aarch64-linux-gnu \
    g++-aarch64-linux-gnu \
    pkg-config \
    libtool \
    libtool-bin \
    python3-distutils \
    autogen \
    zip \
    python3.6 python3.6-dev \
    python3-pip

RUN pip3 install --upgrade pip && \
    pip3 install --upgrade setuptools && \
    pip3 install torch==1.9.1+cu111 torchvision==0.10.1+cu111 -f https://download.pytorch.org/whl/torch_stable.html && \
    pip3 install --extra-index-url https://developer.download.nvidia.com/compute/redist --upgrade nvidia-dali-cuda110 && \
    pip3 install mlperf_compliance && \
    pip3 install pycocotools

WORKDIR ${WORK_DIR}

RUN git clone https://github.com/NVIDIA/apex.git && \
    cd apex && \
    pip3 install -v --disable-pip-version-check --no-cache-dir --global-option="--cpp_ext" --global-option="--cuda_ext" ./ && \
    cd ${WORK_DIR}

RUN git clone https://github.com/rsek147/DALI-SSD.git dali-ssd

RUN apt-get clean && rm -rf /root/.cache/pip
