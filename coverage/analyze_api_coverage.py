#!/usr/bin/env python3
"""
API覆盖率分析工具
使用libclang提取头文件API，并分析测试文件覆盖情况
"""

import json
import os
import re
from collections import defaultdict

import clang.cindex
from clang.cindex import AccessSpecifier, CursorKind

# 设置libclang库路径
clang.cindex.Config.set_library_file(
    "/usr/lib/x86_64-linux-gnu/libclang-14.so.1"
)


def log(msg):
    """实时日志输出"""
    print(msg, flush=True)


def get_access_specifier_name(access):
    """获取访问修饰符名称"""
    if access == AccessSpecifier.PUBLIC:
        return "public"
    elif access == AccessSpecifier.PROTECTED:
        return "protected"
    elif access == AccessSpecifier.PRIVATE:
        return "private"
    return "unknown"


def get_function_signature(cursor):
    """获取函数完整签名"""
    result_type = cursor.result_type.spelling if cursor.result_type else ""
    name = cursor.spelling

    params = []
    for child in cursor.get_children():
        if child.kind == CursorKind.PARM_DECL:
            param_type = child.type.spelling
            param_name = child.spelling
            if param_name:
                params.append(f"{param_type} {param_name}")
            else:
                params.append(param_type)

    params_str = ", ".join(params)
    signature = f"{result_type} {name}({params_str})"

    return signature


def extract_functions_from_class(cursor, class_name, namespace=""):
    """从类中提取所有成员函数"""
    functions = []

    for child in cursor.get_children():
        if child.kind in [
            CursorKind.CXX_METHOD,
            CursorKind.CONSTRUCTOR,
            CursorKind.DESTRUCTOR,
            CursorKind.CONVERSION_FUNCTION,
            CursorKind.FUNCTION_TEMPLATE,
        ]:
            func_info = {
                "name": child.spelling,
                "kind": child.kind.name,
                "signature": get_function_signature(child),
                "return_type": child.result_type.spelling
                if child.result_type
                else "",
                "access": get_access_specifier_name(child.access_specifier),
                "class_name": class_name,
                "namespace": namespace,
                "is_template": child.kind == CursorKind.FUNCTION_TEMPLATE,
                "parameters": [],
            }

            for param in child.get_children():
                if param.kind == CursorKind.PARM_DECL:
                    func_info["parameters"].append(
                        {"name": param.spelling, "type": param.type.spelling}
                    )

            functions.append(func_info)

    return functions


def traverse_ast(cursor, target_file, namespace_stack=None):
    """遍历AST树，提取所有函数和类"""
    if namespace_stack is None:
        namespace_stack = []

    results = {"classes": {}, "free_functions": [], "namespaces": set()}

    current_namespace = "::".join(namespace_stack)

    for child in cursor.get_children():
        # 只处理目标文件中的内容
        if child.location.file and target_file not in str(
            child.location.file.name
        ):
            continue

        if child.kind == CursorKind.NAMESPACE:
            new_namespace_stack = [*namespace_stack, child.spelling]
            results["namespaces"].add("::".join(new_namespace_stack))
            sub_results = traverse_ast(child, target_file, new_namespace_stack)

            results["classes"].update(sub_results["classes"])
            results["free_functions"].extend(sub_results["free_functions"])
            results["namespaces"].update(sub_results["namespaces"])

        elif child.kind in [
            CursorKind.CLASS_DECL,
            CursorKind.STRUCT_DECL,
            CursorKind.CLASS_TEMPLATE,
        ]:
            if child.is_definition():
                class_name = child.spelling
                full_class_name = (
                    f"{current_namespace}::{class_name}"
                    if current_namespace
                    else class_name
                )

                class_info = {
                    "name": class_name,
                    "full_name": full_class_name,
                    "namespace": current_namespace,
                    "kind": child.kind.name,
                    "methods": extract_functions_from_class(
                        child, class_name, current_namespace
                    ),
                    "base_classes": [],
                }

                for base in child.get_children():
                    if base.kind == CursorKind.CXX_BASE_SPECIFIER:
                        class_info["base_classes"].append(base.type.spelling)

                results["classes"][full_class_name] = class_info

        elif child.kind in [
            CursorKind.FUNCTION_DECL,
            CursorKind.FUNCTION_TEMPLATE,
        ]:
            func_info = {
                "name": child.spelling,
                "kind": child.kind.name,
                "signature": get_function_signature(child),
                "return_type": child.result_type.spelling
                if child.result_type
                else "",
                "access": "global",
                "class_name": None,
                "namespace": current_namespace,
                "is_template": child.kind == CursorKind.FUNCTION_TEMPLATE,
                "parameters": [],
            }

            for param in child.get_children():
                if param.kind == CursorKind.PARM_DECL:
                    func_info["parameters"].append(
                        {"name": param.spelling, "type": param.type.spelling}
                    )

            results["free_functions"].append(func_info)

    return results


def parse_header(header_path, include_paths=None):
    """解析头文件"""
    if include_paths is None:
        include_paths = []

    index = clang.cindex.Index.create()

    args = [
        "-x",
        "c++",
        "-std=c++17",
        "-DPADDLE_WITH_CUDA",
        "-fsyntax-only",  # 只做语法分析
    ]

    for inc_path in include_paths:
        args.append(f"-I{inc_path}")

    try:
        # 使用更简单的解析选项，跳过函数体
        tu = index.parse(
            header_path,
            args=args,
            options=clang.cindex.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES,
        )
        results = traverse_ast(tu.cursor, header_path)
        results["namespaces"] = list(results["namespaces"])
        return results
    except Exception as e:
        log(f"  警告: 解析 {header_path} 失败: {e}")
        return {"classes": {}, "free_functions": [], "namespaces": []}


def parse_all_headers(header_dir, include_paths=None):
    """解析目录下所有头文件"""
    all_apis = {
        "headers": {},
        "all_functions": [],
        "all_classes": {},
        "summary": {
            "total_headers": 0,
            "total_classes": 0,
            "total_methods": 0,
            "total_free_functions": 0,
        },
    }

    # 查找所有头文件
    header_files = []
    for root, dirs, files in os.walk(header_dir):
        for f in files:
            if f.endswith(".h") or f.endswith(".hpp"):
                header_files.append(os.path.join(root, f))

    log(f"找到 {len(header_files)} 个头文件")

    for i, header_path in enumerate(header_files):
        rel_path = os.path.relpath(header_path, header_dir)
        log(f"  [{i + 1}/{len(header_files)}] 解析: {rel_path}")

        results = parse_header(header_path, include_paths)

        all_apis["headers"][rel_path] = results
        all_apis["summary"]["total_headers"] += 1

        # 收集所有类
        for class_name, class_info in results["classes"].items():
            all_apis["all_classes"][class_name] = class_info
            all_apis["summary"]["total_classes"] += 1
            all_apis["summary"]["total_methods"] += len(class_info["methods"])

            # 添加到函数列表
            for method in class_info["methods"]:
                func_record = {
                    **method,
                    "source_file": rel_path,
                    "full_name": f"{class_name}::{method['name']}",
                }
                all_apis["all_functions"].append(func_record)

        # 收集自由函数
        for func in results["free_functions"]:
            func_record = {
                **func,
                "source_file": rel_path,
                "full_name": f"{func['namespace']}::{func['name']}"
                if func["namespace"]
                else func["name"],
            }
            all_apis["all_functions"].append(func_record)
            all_apis["summary"]["total_free_functions"] += 1

    return all_apis


def analyze_test_files(test_dir):
    """分析测试文件，提取调用的API"""
    test_analysis = {
        "files": {},
        "called_functions": set(),
        "called_methods": set(),
        "all_identifiers": set(),
    }

    # 匹配函数调用的模式
    # namespace::function(
    ns_func_pattern = re.compile(r"(?:at|c10|torch|paddle)::(\w+)\s*[<(]")
    # 对象方法调用 obj.method( 或 obj->method(
    method_pattern = re.compile(r"[.)>]\s*(\w+)\s*\(")
    # 直接函数调用
    direct_pattern = re.compile(r"(?<![:\w.>])(\w+)\s*\(")
    # TEST宏
    test_pattern = re.compile(r"TEST(?:_F)?\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)")

    # 需要排除的常见非API调用
    exclude_names = {
        "if",
        "for",
        "while",
        "switch",
        "catch",
        "sizeof",
        "return",
        "TEST",
        "TEST_F",
        "EXPECT_EQ",
        "EXPECT_TRUE",
        "EXPECT_FALSE",
        "EXPECT_GT",
        "EXPECT_LT",
        "EXPECT_GE",
        "EXPECT_LE",
        "EXPECT_NE",
        "ASSERT_EQ",
        "ASSERT_TRUE",
        "ASSERT_FALSE",
        "ASSERT_NE",
        "std",
        "static_cast",
        "dynamic_cast",
        "const_cast",
        "reinterpret_cast",
        "main",
        "printf",
        "cout",
        "cerr",
        "endl",
        "make_shared",
        "make_unique",
        "push_back",
        "size",
        "empty",
        "begin",
        "end",
        "data",
        "get",
        "set",
        "c_str",
        "str",
        "find",
        "substr",
        "length",
        "reserve",
        "resize",
        "value",
        "has_value",
        "reset",
        "emplace",
        "insert",
        "erase",
        "clear",
    }

    # 查找所有测试文件
    test_files = []
    for root, dirs, files in os.walk(test_dir):
        for f in files:
            if f.endswith(".cpp") or f.endswith(".cc") or f.endswith(".cxx"):
                test_files.append(os.path.join(root, f))

    print(f"\n找到 {len(test_files)} 个测试文件")

    for test_file in test_files:
        rel_path = os.path.relpath(test_file, test_dir)
        print(f"  分析: {rel_path}")

        try:
            with open(test_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            print(f"    警告: 读取失败 - {e}")
            continue

        file_info = {"test_cases": [], "called_apis": set()}

        # 提取测试用例名
        for match in test_pattern.finditer(content):
            file_info["test_cases"].append(f"{match.group(1)}.{match.group(2)}")

        # 提取命名空间函数调用
        for match in ns_func_pattern.finditer(content):
            name = match.group(1)
            if name not in exclude_names:
                file_info["called_apis"].add(name)
                test_analysis["called_functions"].add(name)

        # 提取方法调用
        for match in method_pattern.finditer(content):
            name = match.group(1)
            if name not in exclude_names and len(name) > 1:
                file_info["called_apis"].add(name)
                test_analysis["called_methods"].add(name)

        # 提取直接函数调用
        for match in direct_pattern.finditer(content):
            name = match.group(1)
            if name not in exclude_names and len(name) > 1:
                file_info["called_apis"].add(name)
                test_analysis["all_identifiers"].add(name)

        file_info["called_apis"] = list(file_info["called_apis"])
        test_analysis["files"][rel_path] = file_info

    # 转换为列表
    test_analysis["called_functions"] = list(test_analysis["called_functions"])
    test_analysis["called_methods"] = list(test_analysis["called_methods"])
    test_analysis["all_identifiers"] = list(test_analysis["all_identifiers"])

    return test_analysis


def compute_coverage(all_apis, test_analysis):
    """计算覆盖率"""
    # 收集所有被测试中调用的标识符
    tested_names = set()
    tested_names.update(test_analysis["called_functions"])
    tested_names.update(test_analysis["called_methods"])
    tested_names.update(test_analysis["all_identifiers"])

    coverage = {
        "tested": [],
        "untested": [],
        "by_file": {},
        "by_class": {},
        "summary": {
            "total_apis": 0,
            "tested_apis": 0,
            "untested_apis": 0,
            "coverage_rate": 0.0,
        },
    }

    # 分析每个API
    for func in all_apis["all_functions"]:
        name = func["name"]
        source_file = func["source_file"]
        class_name = func.get("class_name")
        access = func.get("access", "unknown")

        # 只统计public的API（或全局函数）
        if access not in ["public", "global"]:
            continue

        # 排除构造函数、析构函数、运算符重载（通常不直接测试）
        if name.startswith("~") or name.startswith("operator"):
            continue

        # 排除内部函数
        if name.startswith("_"):
            continue

        coverage["summary"]["total_apis"] += 1

        # 检查是否被测试
        is_tested = name in tested_names

        api_info = {
            "name": name,
            "full_name": func.get("full_name", name),
            "signature": func.get("signature", ""),
            "source_file": source_file,
            "class_name": class_name,
            "tested": is_tested,
        }

        if is_tested:
            coverage["tested"].append(api_info)
            coverage["summary"]["tested_apis"] += 1
        else:
            coverage["untested"].append(api_info)
            coverage["summary"]["untested_apis"] += 1

        # 按文件统计
        if source_file not in coverage["by_file"]:
            coverage["by_file"][source_file] = {
                "total": 0,
                "tested": 0,
                "untested": 0,
                "apis": [],
            }
        coverage["by_file"][source_file]["total"] += 1
        coverage["by_file"][source_file]["apis"].append(api_info)
        if is_tested:
            coverage["by_file"][source_file]["tested"] += 1
        else:
            coverage["by_file"][source_file]["untested"] += 1

        # 按类统计
        if class_name:
            if class_name not in coverage["by_class"]:
                coverage["by_class"][class_name] = {
                    "total": 0,
                    "tested": 0,
                    "untested": 0,
                    "methods": [],
                }
            coverage["by_class"][class_name]["total"] += 1
            coverage["by_class"][class_name]["methods"].append(api_info)
            if is_tested:
                coverage["by_class"][class_name]["tested"] += 1
            else:
                coverage["by_class"][class_name]["untested"] += 1

    # 计算覆盖率
    if coverage["summary"]["total_apis"] > 0:
        coverage["summary"]["coverage_rate"] = round(
            coverage["summary"]["tested_apis"]
            / coverage["summary"]["total_apis"]
            * 100,
            2,
        )

    return coverage


def generate_report(all_apis, test_analysis, coverage, output_file):
    """生成详细报告"""
    lines = []

    lines.append("=" * 80)
    lines.append("Paddle ATen兼容层 API 测试覆盖率分析报告")
    lines.append("=" * 80)
    lines.append("")

    # 总体统计
    lines.append("## 📊 总体统计")
    lines.append("-" * 60)
    lines.append(f"  头文件数量:        {all_apis['summary']['total_headers']}")
    lines.append(f"  类/结构体数量:     {all_apis['summary']['total_classes']}")
    lines.append(f"  成员函数总数:      {all_apis['summary']['total_methods']}")
    lines.append(
        f"  自由函数数量:      {all_apis['summary']['total_free_functions']}"
    )
    lines.append(f"  测试文件数量:      {len(test_analysis['files'])}")
    lines.append("")

    # 覆盖率统计
    lines.append("## 📈 覆盖率统计 (仅统计public API)")
    lines.append("-" * 60)
    lines.append(f"  总API数量:         {coverage['summary']['total_apis']}")
    lines.append(f"  已测试API:         {coverage['summary']['tested_apis']}")
    lines.append(f"  未测试API:         {coverage['summary']['untested_apis']}")
    lines.append(
        f"  覆盖率:            {coverage['summary']['coverage_rate']}%"
    )
    lines.append("")

    # 按文件统计覆盖率
    lines.append("## 📁 按头文件统计覆盖率")
    lines.append("-" * 60)

    # 按覆盖率排序
    sorted_files = sorted(
        coverage["by_file"].items(),
        key=lambda x: (
            x[1]["tested"] / x[1]["total"] if x[1]["total"] > 0 else 0,
            x[0],
        ),
        reverse=True,
    )

    for file_path, file_info in sorted_files:
        if file_info["total"] == 0:
            continue
        rate = round(file_info["tested"] / file_info["total"] * 100, 1)
        if rate == 100:
            status = "✅"
        elif rate >= 50:
            status = "🔶"
        elif rate > 0:
            status = "⚠️"
        else:
            status = "❌"

        lines.append(f"  {status} {file_path}")
        lines.append(
            f"      {file_info['tested']}/{file_info['total']} ({rate}%)"
        )

    lines.append("")

    # 按类统计
    lines.append("## 📦 按类统计覆盖率")
    lines.append("-" * 60)

    sorted_classes = sorted(
        coverage["by_class"].items(),
        key=lambda x: (
            x[1]["tested"] / x[1]["total"] if x[1]["total"] > 0 else 0
        ),
        reverse=True,
    )

    for class_name, class_info in sorted_classes:
        if class_info["total"] == 0:
            continue
        rate = round(class_info["tested"] / class_info["total"] * 100, 1)
        if rate == 100:
            status = "✅"
        elif rate >= 50:
            status = "🔶"
        elif rate > 0:
            status = "⚠️"
        else:
            status = "❌"

        lines.append(
            f"  {status} {class_name}: {class_info['tested']}/{class_info['total']} ({rate}%)"
        )

    lines.append("")

    # 已测试的API列表
    lines.append("## ✅ 已测试的API列表")
    lines.append("-" * 60)

    tested_by_file = defaultdict(list)
    for api in coverage["tested"]:
        tested_by_file[api["source_file"]].append(api)

    for file_path, apis in sorted(tested_by_file.items()):
        lines.append(f"\n### {file_path}")
        for api in apis:
            class_prefix = (
                f"[{api['class_name']}] " if api["class_name"] else ""
            )
            lines.append(f"  ✓ {class_prefix}{api['name']}")

    lines.append("")

    # 未测试的API列表
    lines.append("## ❌ 未测试的API列表")
    lines.append("-" * 60)

    untested_by_file = defaultdict(list)
    for api in coverage["untested"]:
        untested_by_file[api["source_file"]].append(api)

    for file_path, apis in sorted(untested_by_file.items()):
        lines.append(f"\n### {file_path}")
        for api in apis:
            class_prefix = (
                f"[{api['class_name']}] " if api["class_name"] else ""
            )
            lines.append(f"  ✗ {class_prefix}{api['name']}")
            if api["signature"]:
                sig = api["signature"]
                if len(sig) > 70:
                    sig = sig[:67] + "..."
                lines.append(f"      签名: {sig}")

    lines.append("")

    # 测试文件分析
    lines.append("## 🧪 测试文件分析")
    lines.append("-" * 60)

    for test_file, test_info in sorted(test_analysis["files"].items()):
        lines.append(f"\n### {test_file}")
        lines.append(f"  测试用例数: {len(test_info['test_cases'])}")
        if test_info["test_cases"]:
            for tc in test_info["test_cases"][:10]:
                lines.append(f"    • {tc}")
            if len(test_info["test_cases"]) > 10:
                lines.append(
                    f"    ... 还有 {len(test_info['test_cases']) - 10} 个测试用例"
                )

        lines.append(f"  调用的API数: {len(test_info['called_apis'])}")
        if test_info["called_apis"]:
            sorted_apis = sorted(test_info["called_apis"])[:20]
            lines.append(f"    API: {', '.join(sorted_apis)}")
            if len(test_info["called_apis"]) > 20:
                lines.append(
                    f"    ... 还有 {len(test_info['called_apis']) - 20} 个"
                )

    lines.append("")
    lines.append("=" * 80)
    lines.append("报告结束")
    lines.append("=" * 80)

    report = "\n".join(lines)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)

    return report


def main():
    import argparse

    parser = argparse.ArgumentParser(description="API覆盖率分析工具")
    parser.add_argument("--header-dir", "-H", required=True, help="头文件目录")
    parser.add_argument("--test-dir", "-T", required=True, help="测试文件目录")
    parser.add_argument(
        "--include", "-I", action="append", default=[], help="包含路径"
    )
    parser.add_argument(
        "--output", "-o", default="api_coverage_report.txt", help="输出报告文件"
    )
    parser.add_argument("--json", "-j", default=None, help="输出JSON文件")

    args = parser.parse_args()

    print("=" * 60)
    print("Paddle ATen兼容层 API 覆盖率分析")
    print("=" * 60)

    # 解析头文件
    print(f"\n[1/3] 解析头文件目录: {args.header_dir}")
    all_apis = parse_all_headers(args.header_dir, args.include)

    print(f"\n  总计: {all_apis['summary']['total_headers']} 个头文件")
    print(f"  类: {all_apis['summary']['total_classes']} 个")
    print(f"  成员函数: {all_apis['summary']['total_methods']} 个")
    print(f"  自由函数: {all_apis['summary']['total_free_functions']} 个")

    # 分析测试文件
    print(f"\n[2/3] 分析测试文件目录: {args.test_dir}")
    test_analysis = analyze_test_files(args.test_dir)

    print(f"\n  总计: {len(test_analysis['files'])} 个测试文件")
    print(f"  识别的函数调用: {len(test_analysis['called_functions'])} 个")
    print(f"  识别的方法调用: {len(test_analysis['called_methods'])} 个")

    # 计算覆盖率
    print("\n[3/3] 计算覆盖率...")
    coverage = compute_coverage(all_apis, test_analysis)

    print(f"\n  总API数量: {coverage['summary']['total_apis']}")
    print(f"  已测试: {coverage['summary']['tested_apis']}")
    print(f"  未测试: {coverage['summary']['untested_apis']}")
    print(f"  覆盖率: {coverage['summary']['coverage_rate']}%")

    # 生成报告
    print(f"\n生成报告: {args.output}")
    report = generate_report(all_apis, test_analysis, coverage, args.output)

    # 保存JSON
    if args.json:
        print(f"保存JSON数据: {args.json}")
        json_data = {
            "apis": all_apis,
            "tests": test_analysis,
            "coverage": coverage,
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n报告已保存到: {args.output}")

    return coverage


if __name__ == "__main__":
    main()
