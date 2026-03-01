#!/bin/bash
#
# Paddle compat 目录覆盖率分析脚本
# 功能：编译项目、运行测试、分析覆盖率，输出未覆盖的头文件和API
#
# 使用方法：
#   cd PaddleCPPAPITest/tools
#   chmod +x coverage_analysis.sh
#   ./coverage_analysis.sh
#

set -e

# ==================== 配置区域 ====================
# 请根据实际环境修改以下路径
PROJECT_ROOT="/ssd2/bingoo/code/PFCC_api_test"
BUILD_DIR="${PROJECT_ROOT}/coverage_build_analysis"
LCOV_BIN="/ssd2/bingoo/package/lcov-2.3.2/bin/lcov"
TORCH_DIR="/ssd2/bingoo/package/libtorch"
PYTHON_ENV="/ssd2/bingoo/py_env/pfcc_api_test/bin/activate"
COMPAT_DIR="/ssd2/bingoo/py_env/pfcc_api_test/lib/python3.12/site-packages/paddle/include/paddle/phi/api/include/compat"

# 输出文件
OUTPUT_DIR="${BUILD_DIR}/coverage_report"
UNCOVERED_FILES_REPORT="${OUTPUT_DIR}/uncovered_files.txt"
UNCOVERED_APIS_REPORT="${OUTPUT_DIR}/uncovered_apis.txt"
SUMMARY_REPORT="${OUTPUT_DIR}/coverage_summary.txt"

# ==================== 颜色定义 ====================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ==================== 辅助函数 ====================
print_header() {
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}================================================================${NC}"
}

print_success() {
    echo -e "${GREEN}[✓] $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[!] $1${NC}"
}

print_error() {
    echo -e "${RED}[✗] $1${NC}"
}

# ==================== 主流程 ====================

print_header "Paddle compat 目录覆盖率分析"
echo ""

# Step 1: 检查环境
print_header "Step 1: 检查环境"

if [ ! -f "$PYTHON_ENV" ]; then
    print_error "Python虚拟环境不存在: $PYTHON_ENV"
    exit 1
fi

if [ ! -f "$LCOV_BIN" ]; then
    print_error "lcov工具不存在: $LCOV_BIN"
    exit 1
fi

if [ ! -d "$COMPAT_DIR" ]; then
    print_error "compat目录不存在: $COMPAT_DIR"
    exit 1
fi

print_success "环境检查通过"

# Step 2: 激活Python环境
print_header "Step 2: 激活Python环境"
source "$PYTHON_ENV"
print_success "已激活: $PYTHON_ENV"

# Step 3: 创建构建目录
print_header "Step 3: 创建构建目录"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
mkdir -p "$OUTPUT_DIR"
cd "$BUILD_DIR"
print_success "构建目录: $BUILD_DIR"

# Step 4: CMake配置
print_header "Step 4: CMake配置（启用覆盖率）"
cmake "${PROJECT_ROOT}/PaddleCPPAPITest" \
    -DTORCH_DIR="$TORCH_DIR" \
    -DENABLE_COVERAGE=ON \
    -G Ninja > cmake.log 2>&1

if [ $? -eq 0 ]; then
    print_success "CMake配置完成"
else
    print_error "CMake配置失败，查看 ${BUILD_DIR}/cmake.log"
    exit 1
fi

# Step 5: 编译
print_header "Step 5: 编译项目"
ninja > build.log 2>&1

if [ $? -eq 0 ]; then
    print_success "编译完成"
else
    print_error "编译失败，查看 ${BUILD_DIR}/build.log"
    exit 1
fi

# Step 6: 运行测试
print_header "Step 6: 运行Paddle测试"
echo ""
TOTAL_TESTS=0
PASSED_TESTS=0

for test in paddle/paddle_*; do
    test_name=$(basename "$test")
    echo -n "  Running $test_name ... "

    result=$($test --gtest_brief=1 2>&1)
    passed=$(echo "$result" | grep -oP '\[\s*PASSED\s*\]\s*\K\d+' || echo "0")

    if echo "$result" | grep -q "PASSED"; then
        echo -e "${GREEN}PASSED${NC} ($passed tests)"
        PASSED_TESTS=$((PASSED_TESTS + passed))
    else
        echo -e "${RED}FAILED${NC}"
    fi

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
done

echo ""
print_success "测试完成: $TOTAL_TESTS 个测试文件执行完毕"

# Step 7: 收集覆盖率
print_header "Step 7: 收集覆盖率数据"

$LCOV_BIN \
    --capture \
    --directory . \
    --output-file coverage_raw.info \
    --ignore-errors mismatch,mismatch \
    --ignore-errors source,source \
    --ignore-errors inconsistent,inconsistent \
    --rc geninfo_unexecuted_blocks=1 \
    > lcov.log 2>&1

if [ -f coverage_raw.info ]; then
    print_success "原始覆盖率数据已生成"
else
    print_error "覆盖率数据生成失败"
    exit 1
fi

# Step 8: 筛选compat目录
print_header "Step 8: 筛选compat目录覆盖率"

$LCOV_BIN \
    --extract coverage_raw.info "${COMPAT_DIR}/*" \
    --output-file coverage_compat.info \
    --ignore-errors unused,unused \
    >> lcov.log 2>&1

if [ -f coverage_compat.info ]; then
    print_success "compat目录覆盖率已筛选"
else
    print_warning "compat目录覆盖率筛选可能有问题"
fi

# Step 9: 分析并生成报告
print_header "Step 9: 分析覆盖率数据"

python3 << 'PYTHON_SCRIPT'
import os
import re
import subprocess
from collections import defaultdict

COMPAT_DIR = os.environ.get('COMPAT_DIR', '/ssd2/bingoo/py_env/pfcc_api_test/lib/python3.12/site-packages/paddle/include/paddle/phi/api/include/compat')
OUTPUT_DIR = os.environ.get('OUTPUT_DIR', './coverage_report')

# 读取覆盖率数据
coverage_file = 'coverage_compat.info'
covered_files = set()
uncovered_functions = []
covered_functions = []

if os.path.exists(coverage_file):
    with open(coverage_file, 'r') as f:
        content = f.read()

    file_blocks = content.split('end_of_record')
    for block in file_blocks:
        sf_match = re.search(r'SF:(.+)', block)
        if sf_match:
            covered_files.add(sf_match.group(1))

        # 提取未覆盖的函数
        fna_matches = re.findall(r'FNA:(\d+),(\d+),(.+)', block)
        for idx, hit_count, func_name in fna_matches:
            filepath = sf_match.group(1) if sf_match else 'unknown'
            rel_path = filepath.replace(COMPAT_DIR + '/', '')
            if int(hit_count) == 0:
                uncovered_functions.append({
                    'file': rel_path,
                    'function': func_name
                })
            else:
                covered_functions.append({
                    'file': rel_path,
                    'function': func_name,
                    'hit_count': int(hit_count)
                })

# 扫描所有头文件
all_header_files = []
for root, dirs, files in os.walk(COMPAT_DIR):
    for f in files:
        if f.endswith('.h'):
            all_header_files.append(os.path.join(root, f))

# 找出未覆盖的文件
uncovered_header_files = [hf for hf in all_header_files if hf not in covered_files]

# 函数解析
def extract_functions_from_header(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        return []

    func_pattern = r'(?:^|\n)\s*(?:inline\s+)?(?:static\s+)?(?:virtual\s+)?(?:const\s+)?(?:[\w:&*]+(?:<[^>]+>)?)\s+(\w+)\s*\([^)]*\)'
    matches = re.findall(func_pattern, content)
    exclude = ['if', 'while', 'for', 'switch', 'catch', 'return', 'throw', 'sizeof', 'static_assert']
    return [m for m in set(matches) if m not in exclude and not m.startswith('_')]

# demangle函数名
def demangle(mangled_name):
    try:
        result = subprocess.run(['c++filt', mangled_name], capture_output=True, text=True, timeout=5)
        return result.stdout.strip()
    except:
        return mangled_name

# 生成未覆盖文件报告
with open(os.path.join(OUTPUT_DIR, 'uncovered_files.txt'), 'w') as f:
    f.write("=" * 80 + "\n")
    f.write("           未被测试覆盖的头文件列表\n")
    f.write("=" * 80 + "\n\n")
    f.write(f"compat目录总头文件数: {len(all_header_files)}\n")
    f.write(f"已被测试覆盖的文件数: {len(covered_files)}\n")
    f.write(f"未被测试覆盖的文件数: {len(uncovered_header_files)}\n\n")

    uncovered_by_dir = defaultdict(list)
    for hf in sorted(uncovered_header_files):
        rel_path = hf.replace(COMPAT_DIR + '/', '')
        parts = rel_path.split('/')
        dir_name = parts[0] if len(parts) > 1 else 'root'
        uncovered_by_dir[dir_name].append(rel_path)

    for dir_name in sorted(uncovered_by_dir.keys()):
        f.write(f"\n【{dir_name}/】目录 ({len(uncovered_by_dir[dir_name])} 个文件):\n")
        f.write("-" * 60 + "\n")
        for file_path in sorted(uncovered_by_dir[dir_name]):
            f.write(f"  - {file_path}\n")

# 生成未覆盖API报告
with open(os.path.join(OUTPUT_DIR, 'uncovered_apis.txt'), 'w') as f:
    f.write("=" * 80 + "\n")
    f.write("           未被测试覆盖的API列表\n")
    f.write("=" * 80 + "\n\n")

    # Part 1: 已测试文件中未覆盖的函数
    f.write("【Part 1: 已测试文件中未覆盖的函数】\n")
    f.write("-" * 60 + "\n")
    if uncovered_functions:
        for func in uncovered_functions:
            demangled = demangle(func['function'])
            f.write(f"文件: {func['file']}\n")
            f.write(f"  函数: {demangled}\n\n")
    else:
        f.write("  无\n\n")

    # Part 2: 未测试文件中的API
    f.write("\n【Part 2: 完全未被测试的文件中的API】\n")
    f.write("-" * 60 + "\n")

    total_uncovered_apis = 0
    for hf in sorted(uncovered_header_files):
        rel_path = hf.replace(COMPAT_DIR + '/', '')
        funcs = extract_functions_from_header(hf)
        if funcs:
            f.write(f"\n  【{rel_path}】\n")
            for func in sorted(funcs):
                f.write(f"    - {func}()\n")
                total_uncovered_apis += 1

    f.write(f"\n\n未测试文件中的API总数: {total_uncovered_apis}\n")

# 生成摘要报告
with open(os.path.join(OUTPUT_DIR, 'coverage_summary.txt'), 'w') as f:
    f.write("=" * 80 + "\n")
    f.write("              Paddle compat 目录覆盖率分析摘要\n")
    f.write("=" * 80 + "\n\n")

    f.write("【文件覆盖率】\n")
    f.write(f"  总头文件数:       {len(all_header_files)}\n")
    f.write(f"  已覆盖文件数:     {len(covered_files)} ({len(covered_files)*100/len(all_header_files):.1f}%)\n")
    f.write(f"  未覆盖文件数:     {len(uncovered_header_files)} ({len(uncovered_header_files)*100/len(all_header_files):.1f}%)\n\n")

    f.write("【函数覆盖率】\n")
    f.write(f"  已覆盖函数数:     {len(covered_functions)}\n")
    f.write(f"  未覆盖函数数:     {len(uncovered_functions)} (已测试文件中)\n\n")

    f.write("【详细报告文件】\n")
    f.write(f"  未覆盖文件列表:   {os.path.join(OUTPUT_DIR, 'uncovered_files.txt')}\n")
    f.write(f"  未覆盖API列表:    {os.path.join(OUTPUT_DIR, 'uncovered_apis.txt')}\n")
    f.write(f"  覆盖率原始数据:   coverage_compat.info\n")

print(f"报告已生成到: {OUTPUT_DIR}")
PYTHON_SCRIPT

export COMPAT_DIR
export OUTPUT_DIR

print_success "分析完成"

# Step 10: 输出结果
print_header "Step 10: 覆盖率分析结果"
echo ""

# 显示摘要
if [ -f "$SUMMARY_REPORT" ]; then
    cat "$SUMMARY_REPORT"
fi

echo ""
print_header "未覆盖的头文件"
if [ -f "$UNCOVERED_FILES_REPORT" ]; then
    cat "$UNCOVERED_FILES_REPORT"
fi

echo ""
print_header "未覆盖的API"
if [ -f "$UNCOVERED_APIS_REPORT" ]; then
    cat "$UNCOVERED_APIS_REPORT"
fi

echo ""
print_header "完成"
echo -e "${GREEN}所有报告已保存到: ${OUTPUT_DIR}${NC}"
echo ""
echo "报告文件列表:"
echo "  - ${SUMMARY_REPORT}"
echo "  - ${UNCOVERED_FILES_REPORT}"
echo "  - ${UNCOVERED_APIS_REPORT}"
echo "  - ${BUILD_DIR}/coverage_compat.info"
