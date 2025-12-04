#!/usr/bin/env python3
import os
import sys
import re


def parse_coverage_info(info_path):
    """
    解析 coverage.info 文件
    返回结构:
    {
        "file_path": {
            "lines": {line_num: execution_count, ...},
            "functions": {func_name: execution_count, ...},
            "functions_by_line": {line_num: execution_count, ...} # 辅助查找
        },
        ...
    }
    """
    coverage_data = {}
    current_file = None
    current_lines = {}
    current_funcs = {}  # name -> count
    current_funcs_by_line = {}  # line -> count

    # 临时存储 FNL 信息: id -> start_line
    fnl_map = {}

    if not os.path.exists(info_path):
        print(f"Error: Coverage file not found: {info_path}")
        sys.exit(1)

    with open(info_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("SF:"):
                current_file = line[3:]
                current_lines = {}
                current_funcs = {}
                current_funcs_by_line = {}
                fnl_map = {}
            elif line.startswith("DA:"):
                parts = line[3:].split(",")
                if len(parts) >= 2:
                    ln = int(parts[0])
                    cnt = int(parts[1])
                    current_lines[ln] = cnt
            # 处理标准 lcov 格式 FN/FNDA
            elif line.startswith("FN:"):
                parts = line[3:].split(",")
                if len(parts) >= 2:
                    ln = int(parts[0])
                    name = parts[1]
                    # 初始化为0，等待 FNDA 更新，或者如果只有 FN 没有 FNDA 则保持 0
                    if name not in current_funcs:
                        current_funcs[name] = 0
                    # 也可以记录行号映射
                    current_funcs_by_line[ln] = 0  # 初始值，稍后更新
            elif line.startswith("FNDA:"):
                parts = line[5:].split(",")
                if len(parts) >= 2:
                    cnt = int(parts[0])
                    name = parts[1]
                    current_funcs[name] = cnt
                    # 这里比较麻烦，FNDA 没有行号，只能更新 name。
                    # 如果需要通过行号查找，得依赖 FN 记录的映射。

            # 处理 FNL/FNA 格式 (观察到的格式)
            # FNL:id,start_line,end_line
            # FNA:id,count,name
            elif line.startswith("FNL:"):
                parts = line[4:].split(",")
                if len(parts) >= 2:
                    fid = parts[0]
                    start_line = int(parts[1])
                    fnl_map[fid] = start_line
            elif line.startswith("FNA:"):
                parts = line[4:].split(",")
                if len(parts) >= 3:
                    fid = parts[0]
                    cnt = int(parts[1])
                    name = parts[2]
                    current_funcs[name] = cnt
                    if fid in fnl_map:
                        start_line = fnl_map[fid]
                        current_funcs_by_line[start_line] = cnt

            elif line == "end_of_record":
                if current_file:
                    coverage_data[current_file] = {
                        "lines": current_lines,
                        "functions": current_funcs,
                        "functions_by_line": current_funcs_by_line,
                    }
                current_file = None

    return coverage_data


def get_cpp_functions(header_file):
    """
    从 C++ 头文件中提取函数接口。
    """
    funcs = []
    if not os.path.exists(header_file):
        return funcs

    with open(header_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    func_pattern = re.compile(r"(\w+|operator\S+)\s*\(")

    for idx, line in enumerate(lines):
        line_num = idx + 1
        line = line.strip()
        # 跳过注释
        if line.startswith("//") or line.startswith("/*") or line.startswith("*"):
            continue
        # 跳过宏定义
        if line.startswith("#"):
            continue

        # 寻找包含 '(' 和 ')' 的行
        if "(" in line and ")" in line:
            # 排除明显不是函数的结构
            if re.match(r"^\s*(if|for|while|switch|catch)\s*\(", line):
                continue
            # 尝试提取函数名
            # 找到 '(' 之前的一个单词
            match = func_pattern.search(line)
            if match:
                # 排除一些关键字
                name = match.group(1)

                # 过滤常见 C++ 关键字和结构
                keywords = [
                    "if",
                    "for",
                    "while",
                    "switch",
                    "return",
                    "sizeof",
                    "catch",
                    "template",
                    "static_assert",
                    "decltype",
                    "alignof",
                    "typeid",
                    "dynamic_cast",
                    "static_cast",
                    "reinterpret_cast",
                    "const_cast",
                    "new",
                    "delete",
                    "operator",
                    "throw",
                    "noexcept",
                    "explicit",
                ]

                if name in keywords:
                    continue

                # 过滤全大写的宏 (例如 DISABLE_COPY_AND_ASSIGN)
                # 假设通常函数名不会全大写，除非是构造函数恰好全大写（极少）
                # 或者 LOG(INFO) 这种宏
                if name.isupper() and len(name) > 1:
                    continue

                # 特殊处理 placement new: new (storage) Type(...)
                # 如果是 new (xxx)，已经被 keywords 过滤了
                # 但正则可能匹配到 Type (因为前面有 new (storage) )
                # 比如 line 是 "new (storage) EventType(..."
                # 此时正则可能匹配到 EventType
                # 我们可以检查行首是否包含 new
                if "new" in line and name != "operator":
                    # 简单的 heuristic: 如果这一行有 new 且 name 不是 new，可能是构造调用
                    # 但在覆盖率中，这通常算作执行代码行，而不是函数定义
                    # 如果我们只关心“函数接口统计”，这行代码只是调用，不是定义
                    # 函数定义通常以返回值开头，或者类名开头
                    # 忽略函数体内调用的函数（这很难完全做到，但可以尝试过滤缩进过深的？）
                    pass

                # 进一步清理函数名
                clean_name = name.strip("*&")

                funcs.append((line_num, clean_name, line))

    return funcs


def match_file(header_path, coverage_data):
    """
    在 coverage_data 中查找匹配的文件路径
    """
    # 1. 尝试完全匹配
    if header_path in coverage_data:
        return header_path

    # 2. 尝试绝对路径匹配
    abs_path = os.path.abspath(header_path)
    if abs_path in coverage_data:
        return abs_path

    # 3. 智能模糊匹配 (最长公共后缀匹配)
    # 将路径分割为组件列表
    header_parts = abs_path.replace("\\", "/").strip("/").split("/")
    header_name = header_parts[-1]

    best_match = None
    max_overlap = 0

    for cov_path in coverage_data:
        # 简单优化：如果文件名都不匹配，跳过
        if not cov_path.endswith(header_name):
            continue

        cov_parts = cov_path.replace("\\", "/").strip("/").split("/")

        if cov_parts[-1] != header_name:
            continue

        # 计算从后往前的重叠组件数
        overlap = 0
        min_len = min(len(header_parts), len(cov_parts))
        for i in range(1, min_len + 1):
            if header_parts[-i] == cov_parts[-i]:
                overlap += 1
            else:
                break

        # 记录最佳匹配
        if overlap > max_overlap:
            max_overlap = overlap
            best_match = cov_path

    # 匹配阈值：
    # 1. 只有文件名匹配 (overlap=1): 风险较高，但如果没有更好的选择且文件名独特，也可以接受
    # 2. 文件名+父目录匹配 (overlap>=2): 可信度较高
    # 对于本例 ATen/ops/abs.h，overlap 应该是 3，非常匹配
    if best_match and max_overlap >= 1:
        return best_match

    return None


def main():
    if len(sys.argv) != 3:
        print(f"Usage: python {sys.argv[0]} <header_folder> <coverage.info>")
        sys.exit(1)

    header_folder = sys.argv[1]
    coverage_file = sys.argv[2]

    print("Parsing coverage info...")
    cov_data = parse_coverage_info(coverage_file)
    print(f"Loaded coverage data for {len(cov_data)} files.")

    headers_stats = []

    # 1. 递归读取头文件
    print(f"Scanning headers in {header_folder}...")
    for root, dirs, files in os.walk(header_folder):
        for file in files:
            if file.endswith(".h") or file.endswith(".hpp") or file.endswith(".cuh"):
                full_path = os.path.join(root, file)
                # 提取函数
                funcs = get_cpp_functions(full_path)

                # 2. 查找覆盖率
                matched_key = match_file(full_path, cov_data)

                file_stat = {
                    "path": full_path,
                    "matched_in_coverage": False,
                    "line_coverage_pct": 0.0,
                    "total_lines": 0,
                    "covered_lines": 0,
                    "funcs_total": len(funcs),
                    "funcs_executed": [],
                    "funcs_not_executed": [],
                    "all_funcs_extracted": funcs,
                }

                if matched_key:
                    file_stat["matched_in_coverage"] = True
                    file_cov = cov_data[matched_key]

                    lines_info = file_cov["lines"]
                    total_instrumented = len(lines_info)
                    covered_count = sum(1 for c in lines_info.values() if c > 0)

                    if total_instrumented > 0:
                        file_stat["line_coverage_pct"] = (
                            covered_count / total_instrumented
                        ) * 100
                    file_stat["total_lines"] = total_instrumented
                    file_stat["covered_lines"] = covered_count

                    funcs_by_line = file_cov.get("functions_by_line", {})

                    for ln, fname, raw_line in funcs:
                        is_executed = False

                        found_in_fn_record = False
                        # 扩大搜索范围以匹配可能的行号差异
                        for offset in range(-2, 3):
                            target_ln = ln + offset
                            if target_ln in funcs_by_line:
                                found_in_fn_record = True
                                if funcs_by_line[target_ln] > 0:
                                    is_executed = True
                                break

                        if not found_in_fn_record:
                            # 如果没有函数记录，检查行覆盖
                            # 检查函数声明行或后续几行（应对多行声明）
                            for offset in range(0, 3):
                                if (ln + offset) in lines_info and lines_info[
                                    ln + offset
                                ] > 0:
                                    is_executed = True
                                    break

                        if is_executed:
                            file_stat["funcs_executed"].append(fname)
                        else:
                            file_stat["funcs_not_executed"].append(fname)

                else:
                    for _, fname, _ in funcs:
                        file_stat["funcs_not_executed"].append(fname)

                headers_stats.append(file_stat)

    # 4. 打印报告
    print("\n" + "=" * 80)
    print("COVERAGE ANALYSIS REPORT")
    print("=" * 80)

    print(f"{'File':<60} | {'Line Cov':<10} | {'Funcs Exec/Total'}")
    print("-" * 90)

    not_covered_files = []

    for stat in headers_stats:
        display_path = stat["path"]
        if len(display_path) > 60:
            display_path = "..." + display_path[-57:]

        executed = len(stat["funcs_executed"])
        total = stat["funcs_total"]
        pct = stat["line_coverage_pct"]

        print(f"{display_path:<60} | {pct:>8.2f}% | {executed}/{total}")

        if pct == 0 and total > 0:
            not_covered_files.append(stat["path"])

    print("\n" + "=" * 80)
    print(
        "FILES WITH 0% LINE COVERAGE "
        "(Instrumented lines not covered or file not found in info)"
    )
    for f in not_covered_files:
        print(f"  - {f}")

    # print("\n" + "="*80)
    # print("UNEXECUTED FUNCTIONS (Sample)")
    # count = 0
    # for stat in headers_stats:
    #     if stat["funcs_not_executed"]:
    #         print(f"\nFile: {stat['path']}")
    #         for func in stat["funcs_not_executed"]:
    #             print(f"  [X] {func}")
    #             count += 1
    #             if count > 100:
    #                 print("  ... (too many to list)")
    #                 break
    #     if count > 100:
    #         break

    # if count > 100:
    #     print(f"\n... Total unexecuted functions truncated.")


if __name__ == "__main__":
    main()
