#!/usr/bin/env python3
"""
demangle_fna_simple.py - 简化的 FNA 解析器
"""

import re
import sys
import subprocess


def demangle_cpp_name(mangled_name):
    """使用 c++filt 解析 C++ 函数名"""
    try:
        result = subprocess.run(
            ["c++filt"], input=mangled_name, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except:
        return mangled_name


def extract_simple_name(demangled_name: str) -> str:
    """从完整函数名中提取简单函数名（最后一个::之后的部分）"""
    if "::" in demangled_name:
        # 分割并获取最后一部分
        parts = demangled_name.split("::")
        return parts[-1]
    return demangled_name


def process_fna_line(line):
    """处理包含 FNA: 模式的单行"""
    # 匹配 FNA:数字,数字,mangled_name
    pattern = r"(FNA:\s*[^,]+,\s*[^,]+,\s*)([^,\s]+)"

    def replace_match(match):
        prefix = match.group(1)  # FNA:0,78,
        mangled = match.group(2)  # _ZN...

        demangled = demangle_cpp_name(mangled)
        demangled = extract_simple_name(demangled)
        # 如果解析失败，保持原样
        if demangled == mangled or not demangled:
            return match.group(0)

        return f"{prefix}{demangled}"

    # 使用正则替换所有匹配
    return re.sub(pattern, replace_match, line, flags=re.IGNORECASE)


def main():
    print("=====")
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <输入文件> [输出文件]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = (
        sys.argv[2]
        if len(sys.argv) > 2
        else f"{input_file.rsplit('.', 1)[0]}_demangled.txt"
    )

    try:
        with open(input_file, "r", encoding="utf-8") as f_in:
            with open(output_file, "w", encoding="utf-8") as f_out:
                line_count = 0
                processed_count = 0

                for line in f_in:
                    line_count += 1

                    if "FNA:" in line.upper():
                        processed_line = process_fna_line(line)
                        if processed_line != line:
                            processed_count += 1
                        f_out.write(processed_line)
                    else:
                        f_out.write(line)

        print(f"输入文件: {input_file}")
        print(f"输出文件: {output_file}")
        print(f"总行数: {line_count}")
        print(f"处理行数: {processed_count}")

    except FileNotFoundError:
        print(f"错误: 文件不存在 - {input_file}")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
