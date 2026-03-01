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
cd /ssd2/bingoo/code/PFCC_api_test
source paddle_env/bin/activate
python3 tools/analyze_api_coverage.py \
    --header-dir /ssd2/bingoo/py_env/pfcc_api_test/lib/python3.12/site-packages/paddle/include/paddle/phi/api/include/compat \
    -I /ssd2/bingoo/py_env/pfcc_api_test/lib/python3.12/site-packages/paddle/include \
    -I /ssd2/bingoo/py_env/pfcc_api_test/lib/python3.12/site-packages/paddle/include/paddle/phi/api/include/compat \
    --test-dir /ssd2/bingoo/code/PFCC_api_test/PaddleCPPAPITest/test     \
    --output api_coverage_report.txt     \
    --json api_coverage_report.json
