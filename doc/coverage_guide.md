# Paddle compat 目录覆盖率测试指南

本文档描述如何运行 PaddleCPPAPITest 项目的测试用例，并生成 Paddle compat 目录的代码覆盖率报告。

## 概述

PaddleCPPAPITest 是一个测试框架，用于验证 PaddlePaddle 和 PyTorch C++ API 的兼容性。通过运行 paddle 前缀的测试可执行文件，可以收集 Paddle compat 目录下头文件的覆盖率数据。

## 环境要求

### 依赖工具
- CMake >= 3.18
- Ninja 构建工具
- GCC/G++ (支持 C++17)
- lcov >= 2.0 (用于生成覆盖率报告)
- Python 3.x

### 环境配置
```bash
# 激活 Python 虚拟环境
source /ssd2/bingoo/py_env/pfcc_api_test/bin/activate
```

## 完整执行流程

### 1. 创建构建目录并配置 CMake

```bash
# 进入项目根目录
cd /ssd2/bingoo/code/PFCC_api_test

# 创建覆盖率专用构建目录
rm -rf coverage_build_compat
mkdir coverage_build_compat && cd coverage_build_compat

# 激活环境
source /ssd2/bingoo/py_env/pfcc_api_test/bin/activate

# 配置 CMake，启用覆盖率选项
cmake ../PaddleCPPAPITest \
    -DTORCH_DIR=/ssd2/bingoo/package/libtorch \
    -DENABLE_COVERAGE=ON \
    -G Ninja
```

关键参数说明：
- `-DTORCH_DIR`: libtorch 安装路径
- `-DENABLE_COVERAGE=ON`: 启用覆盖率编译选项（添加 `-fprofile-arcs -ftest-coverage` 编译标志）
- `-G Ninja`: 使用 Ninja 作为构建系统

### 2. 编译项目

```bash
ninja
```

编译成功后，会在以下目录生成可执行文件：
- `paddle/`: Paddle 测试可执行文件
- `torch/`: PyTorch 测试可执行文件

### 3. 运行 Paddle 测试

运行所有 paddle 前缀的测试可执行文件：

```bash
# 运行所有 paddle 测试
for test in paddle/paddle_*; do
    echo "Running: $(basename $test)"
    $test --gtest_brief=1
done
```

测试文件列表：
| 测试文件 | 测试内容 |
|---------|---------|
| paddle_AbsTest | abs 操作测试 |
| paddle_ArangeTest | arange 操作测试 |
| paddle_ConnectionOpsTest | 连接操作测试 |
| paddle_CreationOpsTest | 张量创建操作测试 |
| paddle_FlattenTest | flatten 操作测试 |
| paddle_FromBlobTest | from_blob 操作测试 |
| paddle_NarrowTest | narrow 操作测试 |
| paddle_ReshapeTest | reshape 操作测试 |
| paddle_ScalarTypeTest | 标量类型测试 |
| paddle_StorageTest | Storage 类测试 |
| paddle_SumTest | sum 操作测试 |
| paddle_TensorTest | Tensor 基础功能测试 |
| paddle_TensorTest_compare | Tensor 对比测试 |

### 4. 收集覆盖率数据

使用 lcov 收集 gcov 数据：

```bash
COMPAT_DIR="/ssd2/bingoo/py_env/pfcc_api_test/lib/python3.12/site-packages/paddle/include/paddle/phi/api/include/compat"

# 收集原始覆盖率数据
/ssd2/bingoo/package/lcov-2.3.2/bin/lcov \
    --capture \
    --directory . \
    --output-file coverage_raw.info \
    --ignore-errors mismatch,mismatch \
    --ignore-errors source,source \
    --ignore-errors inconsistent,inconsistent \
    --rc geninfo_unexecuted_blocks=1
```

### 5. 筛选 compat 目录覆盖率

从原始数据中提取 compat 目录的覆盖率：

```bash
/ssd2/bingoo/package/lcov-2.3.2/bin/lcov \
    --extract coverage_raw.info "${COMPAT_DIR}/*" \
    --output-file coverage_compat.info \
    --ignore-errors unused,unused
```

### 6. 查看覆盖率摘要

```bash
/ssd2/bingoo/package/lcov-2.3.2/bin/lcov --summary coverage_compat.info
```

### 7. 生成 HTML 报告（可选）

```bash
/ssd2/bingoo/package/lcov-2.3.2/bin/genhtml \
    coverage_compat.info \
    --output-directory coverage_html \
    --title "Paddle compat API Coverage"
```

## 覆盖率报告示例

### 总体覆盖率

| 指标 | 覆盖率 | 详情 |
|------|--------|------|
| **行覆盖率** | 85.7% | 312/364 行 |
| **函数覆盖率** | 98.4% | 122/124 函数 |
| 覆盖文件数 | 24个 | - |

### 各目录覆盖率

#### ATen/ 目录 (核心 Tensor 操作)
- 行覆盖率: 94.8% (221/233)
- 函数覆盖率: 98.7% (77/78)

主要文件：
- `ATen/core/TensorBase.h` - 97.4% 行覆盖
- `ATen/core/TensorBody.h` - 90.0% 行覆盖
- `ATen/ops/*.h` - 各操作头文件均为 100% 覆盖

#### c10/ 目录 (基础类型和工具)
- 行覆盖率: 75.2% (85/113)
- 函数覆盖率: 97.4% (38/39)

主要文件：
- `c10/core/ScalarType.h` - 38.6% 行覆盖（包含大量数据类型转换，部分类型未测试）
- `c10/core/TensorOptions.h` - 96.8% 行覆盖
- 其他 c10 文件 - 100% 覆盖

#### utils/ 目录 (工具函数)
- 行覆盖率: 33.3% (6/18)
- 函数覆盖率: 100% (3/3)

主要文件：
- `utils/int_array_ref_conversion.h` - 100% 行覆盖
- `utils/scalar_type_conversion.h` - 25.0% 行覆盖

## 一键执行脚本

### 方法一：使用覆盖率分析脚本（推荐）

项目提供了完整的覆盖率分析脚本，可以自动完成编译、测试、分析并输出未覆盖的头文件和API：

```bash
# 进入项目目录
cd PaddleCPPAPITest/tools

# 运行分析脚本
./coverage_analysis.sh
```

脚本会自动：
1. 检查环境配置
2. 创建构建目录并编译（启用覆盖率）
3. 运行所有 Paddle 测试
4. 收集并分析覆盖率数据
5. 生成三个报告文件：
   - `uncovered_files.txt` - 未覆盖的头文件列表
   - `uncovered_apis.txt` - 未覆盖的API列表
   - `coverage_summary.txt` - 覆盖率摘要

### 方法二：手动执行脚本

将以下脚本保存为 `run_coverage.sh`：

```bash
#!/bin/bash
set -e

PROJECT_ROOT="/ssd2/bingoo/code/PFCC_api_test"
BUILD_DIR="${PROJECT_ROOT}/coverage_build_compat"
LCOV_BIN="/ssd2/bingoo/package/lcov-2.3.2/bin/lcov"
COMPAT_DIR="/ssd2/bingoo/py_env/pfcc_api_test/lib/python3.12/site-packages/paddle/include/paddle/phi/api/include/compat"

# 激活环境
source /ssd2/bingoo/py_env/pfcc_api_test/bin/activate

# 清理并创建构建目录
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

# 配置 CMake
echo "=== 配置 CMake ==="
cmake ../PaddleCPPAPITest \
    -DTORCH_DIR=/ssd2/bingoo/package/libtorch \
    -DENABLE_COVERAGE=ON \
    -G Ninja

# 编译
echo "=== 编译项目 ==="
ninja

# 运行测试
echo "=== 运行 Paddle 测试 ==="
for test in paddle/paddle_*; do
    echo "Running: $(basename $test)"
    $test --gtest_brief=1 2>&1 | grep -E '(PASSED|FAILED|tests)'
done

# 收集覆盖率
echo "=== 收集覆盖率数据 ==="
${LCOV_BIN} \
    --capture \
    --directory . \
    --output-file coverage_raw.info \
    --ignore-errors mismatch,mismatch \
    --ignore-errors source,source \
    --ignore-errors inconsistent,inconsistent \
    --rc geninfo_unexecuted_blocks=1

# 筛选 compat 目录
echo "=== 筛选 compat 目录覆盖率 ==="
${LCOV_BIN} \
    --extract coverage_raw.info "${COMPAT_DIR}/*" \
    --output-file coverage_compat.info \
    --ignore-errors unused,unused

# 输出摘要
echo "=== 覆盖率摘要 ==="
${LCOV_BIN} --summary coverage_compat.info

echo ""
echo "覆盖率数据已保存到: ${BUILD_DIR}/coverage_compat.info"
```

## 注意事项

1. **编译器版本**：需要使用支持 gcov 的 GCC 编译器
2. **lcov 版本**：建议使用 lcov 2.0 及以上版本，以支持更多错误忽略选项
3. **测试顺序**：需要在收集覆盖率之前运行测试，否则无法生成 gcda 文件
4. **路径配置**：请根据实际环境修改脚本中的路径变量

## 相关链接

- [PaddleCPPAPITest 项目 README](../README.md)
- [lcov 官方文档](https://github.com/linux-test-project/lcov)
- [GCC gcov 文档](https://gcc.gnu.org/onlinedocs/gcc/Gcov.html)

## 附录：未覆盖API完整报告

### Part 1: 已测试文件中未覆盖的函数（2个）

这些函数所在文件已被测试覆盖，但特定函数未被调用：

| 序号 | 函数签名 | 所在文件 | 描述 |
|-----|---------|---------|------|
| 1 | `at::Tensor::pin_memory(std::optional<c10::Device>) const` | ATen/core/TensorBody.h | 将tensor固定到内存，用于GPU数据传输优化 |
| 2 | `c10::toString(c10::ScalarType)` | c10/core/ScalarType.h | 将ScalarType枚举转换为字符串表示 |

### Part 2: 完全未被测试的头文件（52个）

以下头文件完全未被测试用例覆盖：

#### ATen/ 目录（20个文件）

| 文件 | 主要API |
|-----|--------|
| ATen/ATen.h | 主入口头文件 |
| ATen/AccumulateType.h | `toAccumulateType()` |
| ATen/Device.h | Device相关定义 |
| ATen/DeviceGuard.h | `device_of()` |
| ATen/Functions.h | 函数入口 |
| ATen/Tensor.h | Tensor别名 |
| ATen/Utils.h | 工具函数 |
| ATen/core/Scalar.h | Scalar类定义 |
| ATen/core/Tensor.h | Tensor核心定义 |
| ATen/core/TensorAccessor.h | `TensorAccessor()`, `GenericPackedTensorAccessor()` 等 |
| ATen/core/ivalue.h | `IValue()`, `is_bool()`, `is_double()`, `get()` 等 (45+函数) |
| ATen/cuda/CUDAContext.h | `getCurrentDeviceProperties()`, `getDeviceProperties()` |
| ATen/cuda/CUDADataType.h | `ScalarTypeToCudaDataType()`, `getCudaDataType()` |
| ATen/cuda/EmptyTensor.h | `empty_cuda()` |
| ATen/cuda/Exceptions.h | CUDA异常处理 |
| ATen/indexing.h | `Slice()`, `start()`, `stop()`, `step()` |
| ATen/native/cuda/Resize.h | CUDA Resize操作 |
| ATen/ops/empty_strided.h | `empty_strided()` |
| ATen/ops/tensor.h | `tensor()` |
| ATen/ops/transpose.h | `transpose()`, `perm()` |

#### c10/ 目录（23个文件）

| 文件 | 主要API |
|-----|--------|
| c10/core/Backend.h | Backend枚举定义 |
| c10/core/DeviceType.h | DeviceType枚举 |
| c10/core/Event.h | `Event()`, `CreateCudaEventFromPool()`, `record()` 等 |
| c10/core/Layout.h | Layout相关 |
| c10/core/MemoryFormat.h | MemoryFormat枚举 |
| c10/core/Scalar.h | Scalar类定义 |
| c10/core/SymInt.h | SymInt类 |
| c10/core/SymIntArrayRef.h | SymIntArrayRef类 |
| c10/core/Symfloat.h | Symfloat类 |
| c10/cuda/CUDAException.h | `CompatException`, `what()` |
| c10/cuda/CUDAFunctions.h | `device_synchronize()` |
| c10/cuda/CUDAGuard.h | `CUDAGuard()`, `OptionalCUDAGuard()`, `set_device()` 等 |
| c10/cuda/CUDAStream.h | `CUDAStream()`, `getCurrentCUDAStream()`, `raw_stream()` 等 |
| c10/cuda/PhiloxCudaState.h | `PhiloxCudaState()` |
| c10/macros/Macros.h | 宏定义 |
| c10/util/BFloat16.h | BFloat16类型 |
| c10/util/Exception.h | `C10ThrowImpl()`, `PADDLE_THROW()` |
| c10/util/Float8_e4m3fn.h | Float8_e4m3fn类型 |
| c10/util/Float8_e5m2.h | Float8_e5m2类型 |
| c10/util/Half.h | Half类型 |
| c10/util/Optional.h | Optional工具 |
| c10/util/accumulate.h | `multiply_integers()`, `sum_integers()`, `numelements_*()` |
| c10/util/complex.h | complex类型 |

#### torch/ 目录（8个文件）

| 文件 | 主要API |
|-----|--------|
| torch/csrc/api/include/torch/all.h | 主入口 |
| torch/csrc/api/include/torch/cuda.h | `device_count()`, `is_available()`, `synchronize()` |
| torch/csrc/api/include/torch/nn/functional.h | NN功能函数 |
| torch/csrc/api/include/torch/python.h | `getTHPDtype()`, `py_object_to_dtype()` |
| torch/csrc/api/include/torch/sparse.h | 稀疏张量 |
| torch/csrc/api/include/torch/types.h | 类型定义 |
| torch/extension.h | 扩展入口 |
| torch/library.h | `ClassRegistry()`, `OperatorRegistry()` 等 (67+函数) |

#### utils/ 目录（1个文件）

| 文件 | 主要API |
|-----|--------|
| utils/macros.h | 宏定义 |

### 统计摘要

| 指标 | 数值 |
|-----|------|
| compat目录总头文件数 | 76 |
| 已被测试覆盖的文件数 | 24 (31.6%) |
| 完全未被测试的文件数 | 52 (68.4%) |
| 已测试文件中未覆盖的函数数 | 2 |
| 未测试文件中的API函数数(估计) | 173+ |

### 建议优先补充测试的API

根据重要性和常用程度，建议优先补充以下测试：

1. **核心操作类**
   - `ATen/ops/transpose.h` - transpose操作
   - `ATen/ops/tensor.h` - tensor创建
   - `ATen/ops/empty_strided.h` - strided内存创建

2. **CUDA相关**（如果支持GPU测试）
   - `c10/cuda/CUDAStream.h` - CUDA流管理
   - `c10/cuda/CUDAGuard.h` - CUDA设备守卫
   - `torch/csrc/api/include/torch/cuda.h` - CUDA工具函数

3. **数据类型**
   - `c10/util/Half.h` - 半精度浮点
   - `c10/util/BFloat16.h` - BFloat16类型
   - `ATen/core/ivalue.h` - IValue通用值类型

4. **已覆盖文件中的遗漏函数**
   - `at::Tensor::pin_memory()` - 内存固定
   - `c10::toString(ScalarType)` - 类型转字符串
