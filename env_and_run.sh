#!/bin/bash
set -e  # 出错时退出

echo "=== PFCC C++ API Test Environment Setup ==="

# 1. docker环境设置
echo "Setting up Docker environment..."
export CODE_PATH=$PWD

# 检查Docker是否运行
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker daemon is not running. Please start Docker first."
    exit 1
fi

# 检查容器是否已存在
if docker ps -a | grep -q pp_api_test; then
    echo "Removing existing container..."
    docker stop pp_api_test >/dev/null 2>&1 || true
    docker rm pp_api_test >/dev/null 2>&1 || true
fi

echo "Starting Docker container..."
docker run --gpus all -dit \
    --privileged \
    --cap-add=SYS_PTRACE \
    --network=host \
    --ipc=host \
    --security-opt seccomp=unconfined \
    -v /dev/shm:/dev/shm \
    -v /mnt:/mnt \
    -v ${CODE_PATH}:${CODE_PATH} \
    -e "LANG=en_US.UTF-8" \
    -e "CODE_PATH=${CODE_PATH}" \
    -e "PYTHONIOENCODING=utf-8" \
    --name pp_api_test \
    -w ${CODE_PATH} \
     iregistry.baidu-int.com/paddlecloud/paddlecloud-runenv-ubuntu22.04-online:paddle-v3.2.0-gcc11.4-cuda12.6-cudnn9.5-python3.10

# 2. 在容器内执行所有后续步骤
echo "Running setup commands inside Docker container..."
docker exec pp_api_test bash -c "
set -e
echo '=== Starting setup inside Docker container ==='

# 安装编译工具链
echo 'Installing build essentials...'
apt-get update && apt-get install -y build-essential gcc g++ cmake ninja-build unzip
export CC=/usr/bin/gcc
export CXX=/usr/bin/g++

# download package
echo 'Downloading dependencies...'
mkdir -p /tmp/pacakage
cd /tmp/pacakage
wget -q --show-progress https://paddle-qa.bj.bcebos.com/paddle-pipeline/Develop-GpuAll-LinuxCentos-Gcc11-Cuda126-Cudnn95-Trt105-Py310-Compile/f1b4e1d116dfe857b36e194db649b791f42cf684/paddlepaddle_gpu-3.3.0.dev20251202-cp310-cp310-linux_x86_64.whl
wget -q --show-progress https://download.pytorch.org/libtorch/cu126/libtorch-shared-with-deps-2.9.1%2Bcu126.zip

# decompression package and install paddle
echo 'Decompressing packages...'
find . -maxdepth 1 -name 'libtorch*zip' -exec unzip {} \;
python3 -m pip install --force-reinstall /tmp/pacakage/paddle*whl

# get code
echo 'Cloning repository...'
mkdir -p /tmp/pp_code
cd /tmp/pp_code
git clone https://github.com/PFCCLab/PaddleCppAPITest.git || { echo 'Failed to clone repository'; exit 1; }

# compile and run
echo 'Building project...'
mkdir -p build && cd build
cmake ../PaddleCppAPITest/ -DTORCH_DIR=/tmp/pacakage/libtorch -G Ninja || { echo 'CMake configuration failed'; exit 1; }
ninja || { echo 'Build failed'; exit 1; }

# test
echo 'Running tests...'
echo '--- Running torch tests ---'
./torch/torch_TensorTest
echo '--- Running Paddle tests ---'
./paddle/paddle_TensorTest

echo '=== All tests completed successfully ==='
"

# 3. 清理
echo "Cleaning up..."
docker stop pp_api_test
docker rm pp_api_test

echo "=== Setup completed successfully ==="

