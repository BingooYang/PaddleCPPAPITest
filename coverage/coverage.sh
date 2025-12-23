#!/usr/bin/env bash

# Copyright (c) 2025 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -xe

ROOT_PATH="$( cd "$( dirname "${BASH_SOURCE[0]}")/../" && pwd )"
BUILD_PATH=${2:-$ROOT_PATH/../build}
OUTOUT_DIR=${BASH_SOURCE[0]}
echo $BUILD_PATH
function lcov_init(){
    # install lcov
    if [ ! -f "/root/.cache/lcov-1.14.tar.gz" ];then
        wget -P /home https://paddle-ci.gz.bcebos.com/coverage/lcov-1.14.tar.gz --no-proxy --no-check-certificate || exit 101
        cp /home/lcov-1.14.tar.gz /root/.cache/lcov-1.14.tar.gz
    else
        cp /root/.cache/lcov-1.14.tar.gz /home/lcov-1.14.tar.gz
    fi
    tar -xf /home/lcov-1.14.tar.gz -C /
    cd /lcov-1.14
    make install
    cd -
}

function gen_cpp_covinfo(){
    # run paddle coverage
    cd $BUILD_PATH
    lcov --capture -d ${OUTOUT_DIR} -o coverage.info --rc branch_coverage=0 --ignore-errors inconsistent --ignore-errors source
}

gen_cpp_covinfo

# handle function name
python $ROOT_PATH/coverage/coverage_analysis.py ${OUTOUT_DIR}/coverage.info

# print report
python $ROOT_PATH/coverage/coverage_analysis.py ${OUTOUT_DIR}/coverage_demangled.txt
