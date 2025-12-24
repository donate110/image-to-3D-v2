FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# CUDA arch list for torch ( 8.0 A100 - 8.6 A40, A6000 -  8.9 6000 ADA - 12.0 6000 PRO BW)
ENV TORCH_CUDA_ARCH_LIST="8.6;8.0;8.9;12.0"

RUN apt update -y &&  \
    apt-get install software-properties-common -y &&  \
    apt update -y &&  \
    add-apt-repository ppa:deadsnakes/ppa -y &&  \
    apt update -y  &&\
    apt install -y wget gnupg

RUN wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb && \
    dpkg -i cuda-keyring_1.1-1_all.deb && \
    rm cuda-keyring_1.1-1_all.deb

# Install basic system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    git \
    build-essential \
    cmake \
    ninja-build \
    python3.11  \
    python3-pip  \
    python3-wheel \
    libjpeg-dev \
    libpng-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    bash \
    cuda-toolkit-12-8 \
    cuda-nvcc-12-8 \
    cuda-libraries-dev-12-8 \
    cuda-nvtx-12-8 \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 120 &&  \
update-alternatives --install /usr/bin/python python /usr/bin/python3 120

ENV LD_LIBRARY_PATH=/usr/lib64:$LD_LIBRARY_PATH

# Set CUDA environment variables
ENV CUDA_HOME=/usr/local/cuda-12.8
ENV PATH=$CUDA_HOME/bin:$PATH
ENV LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# Copy the project first (needed for trellis2 setup script)
COPY pipeline_service /workspace

# Copy requirements files
COPY docker/requirements.txt /tmp/requirements.txt

# Install basic dependencies from requirements.txt
RUN pip install -r /tmp/requirements.txt

# Install SPZ
RUN wget https://github.com/404-Repo/spz/releases/download/v.0.1.2/pyspz-wheels-ubuntu-latest.zip && \
    unzip pyspz-wheels-ubuntu-latest.zip && \
    pip install pyspz-1.0.0-cp311-cp311-manylinux_2_34_x86_64.whl && \
    rm -rf pyspz-wheels-ubuntu-latest.zip *.whl

# Install ben2
RUN pip install -e "git+https://github.com/PramaLLC/BEN2.git#egg=ben2"

# Install only basic non-GPU dependencies during build
# GPU-dependent packages (flash-attn, nvdiffrast, etc.) will be installed at runtime
WORKDIR /workspace/libs/trellis2
RUN pip install imageio imageio-ffmpeg tqdm easydict opencv-python-headless ninja trimesh transformers gradio==6.0.1 tensorboard pandas lpips zstandard && \
    pip install git+https://github.com/EasternJournalist/utils3d.git@9a4eb15e4021b67b12c460c7057d642626897ec8 && \
    apt install -y libjpeg-dev && \
    pip install pillow-simd kornia timm

# Set working directory back to /workspace
WORKDIR /workspace

# Copy entrypoint script
COPY docker/entrypoint.sh /workspace/entrypoint.sh
RUN chmod +x /workspace/entrypoint.sh

EXPOSE 10006
ENTRYPOINT ["/workspace/entrypoint.sh"]