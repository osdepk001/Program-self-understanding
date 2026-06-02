from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Optional

import yaml

from .parser.python_parser import PythonParser
from .parser.js_parser import JSParser
from .parser.generic_parser import GenericParser
from .analyzer.llm_client import LLMAnalyzer
from .analyzer.incremental_cache import IncrementalCache
from .analyzer.rule_engine import RuleEngine, RuleResult
from .graph.dependency_graph import DependencyGraph, FileNode
from .reporter.json_reporter import JSONReporter
from .reporter.markdown_reporter import MarkdownReporter
from .reporter.html_reporter import HTMLReporter


SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".hxx": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
    ".lua": "lua",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".dart": "dart",
    ".scala": "scala",
    ".pl": "perl",
    ".pm": "perl",
    ".ex": "elixir",
    ".exs": "elixir",
    ".hs": "haskell",
    ".lhs": "haskell",
    ".zig": "zig",
    ".r": "rlang",
    ".R": "rlang",
    ".groovy": "groovy",
    ".m": "objective_c",
    ".mm": "objective_c",
    ".nim": "nim",
    ".clj": "clojure",
    ".cljs": "clojure",
    ".cljc": "clojure",
    ".edn": "clojure",
    ".erl": "erlang",
    ".hrl": "erlang",
    ".sol": "solidity",
}


def load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        print(f"[警告] 配置文件 {config_path} 不存在，使用默认配置")
        return _default_config()

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _default_config() -> dict:
    return {
        "analyzer": {
            "language": "auto",
            "target_dir": ".",
            "exclude_dirs": ["__pycache__", "node_modules", ".git", ".venv", "venv", ".idea", ".vscode", "dist", "build", "output"],
            "exclude_patterns": ["*.pyc", "*.min.js", "*.bundle.js"],
        },
        "llm": {
            "enabled": False,
        },
        "output": {
            "dir": "./output",
            "format": "both",
            "include_mermaid": True,
            "include_html": True,
        },
    }


def scan_files(root: Path, config: dict) -> list[Path]:
    analyzer_cfg = config.get("analyzer", {})
    exclude_dirs = set(analyzer_cfg.get("exclude_dirs", []))
    exclude_patterns = analyzer_cfg.get("exclude_patterns", [])

    files: list[Path] = []
    for entry in root.rglob("*"):
        if not entry.is_file():
            continue

        parts = entry.relative_to(root).parts
        if any(d in exclude_dirs for d in parts):
            continue

        if any(entry.match(p) for p in exclude_patterns):
            continue

        if entry.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(entry)

    return files


def detect_language(files: list[Path], config: dict) -> str:
    lang = config.get("analyzer", {}).get("language", "auto")
    if lang != "auto":
        return lang

    ext_counts: dict[str, int] = {}
    for f in files:
        ext = f.suffix.lower()
        lang_name = SUPPORTED_EXTENSIONS.get(ext, "")
        if lang_name:
            ext_counts[lang_name] = ext_counts.get(lang_name, 0) + 1

    if not ext_counts:
        return "python"

    return max(ext_counts, key=ext_counts.get)


def run_analysis(config: dict, project_root: str) -> DependencyGraph:
    root = Path(project_root).resolve()
    print(f"[信息] 项目根目录: {root}")

    files = scan_files(root, config)
    print(f"[信息] 发现 {len(files)} 个可分析文件")

    grouped = _group_by_language(files)
    for lang, lang_files in grouped.items():
        print(f"  - {lang}: {len(lang_files)} 个文件")

    graph = DependencyGraph()
    cache = IncrementalCache(str(root / ".analysis_cache.json"))
    cache_stats = cache.get_stats()

    valid_abs_paths: set[str] = set()
    valid_rel_paths: set[str] = set()
    for f in files:
        valid_abs_paths.add(str(f.resolve()))
        valid_rel_paths.add(str(f.relative_to(root)).replace(os.sep, "/"))

    changed_count = 0
    cached_count = 0

    for lang, lang_files in grouped.items():
        if lang == "python":
            parser = PythonParser(str(root))
        elif lang in ("javascript", "typescript"):
            parser = JSParser(str(root))
        elif lang in ("go", "rust", "java", "php", "c", "cpp", "csharp", "ruby", "kotlin", "swift", "lua", "shell", "dart", "scala", "perl", "elixir", "haskell", "zig", "rlang", "groovy", "objective_c", "nim", "clojure", "erlang", "solidity"):
            generic = GenericParser(str(root))
        else:
            continue

        for file_path in lang_files:
            abs_str = str(file_path.resolve())
            rel_path = str(file_path.relative_to(root)).replace(os.sep, "/")

            if cache.file_changed(abs_str) or not cache.get_cached_node(rel_path):
                if lang in ("go", "rust", "java", "php", "c", "cpp", "csharp", "ruby", "kotlin", "swift", "lua", "shell", "dart", "scala", "perl", "elixir", "haskell", "zig", "rlang", "groovy", "objective_c", "nim", "clojure", "erlang", "solidity"):
                    node = generic.parse_file(str(file_path), lang)
                else:
                    node = parser.parse_file(str(file_path))
                if node:
                    graph.add_node(node)
                    cache.put_node(rel_path, node.to_dict())
                    changed_count += 1
            else:
                cached_data = cache.get_cached_node(rel_path)
                if cached_data:
                    node = FileNode(
                        path=cached_data.get("path", abs_str),
                        relative_path=cached_data.get("relative_path", rel_path),
                        language=cached_data.get("language", lang),
                        purpose=cached_data.get("purpose", ""),
                        purpose_source=cached_data.get("purpose_source", "cached"),
                        imports=cached_data.get("imports", []),
                        lines=cached_data.get("lines", 0),
                    )
                    graph.add_node(node)
                    cached_count += 1

            cache.update_hash(abs_str)

    cache.remove_stale_entries(valid_abs_paths, valid_rel_paths)
    cache.save()

    if changed_count > 0 or cached_count > 0:
        print(f"[信息] 增量分析: 重新解析 {changed_count} 个, 缓存复用 {cached_count} 个")

    print(f"[信息] 成功解析 {len(graph.get_all_nodes())} 个文件")

    graph.build_reverse_dependencies()
    graph.detect_cycles()
    graph.detect_layers()
    print("[信息] 依赖关系图构建完成")
    cycles = graph.get_cycles()
    if cycles:
        print(f"[警告] 发现 {len(cycles)} 个循环依赖")

    llm_cfg = config.get("llm", {})
    if llm_cfg.get("enabled", False):
        print("[信息] 启动 LLM 分析...")
        llm_analyzer = LLMAnalyzer(llm_cfg)
        if llm_analyzer.enabled:
            llm_analyzer.analyze(graph)
            print("[信息] LLM 分析完成")
        else:
            print("[警告] LLM 未启用：缺少 API Key 或 openai 库未安装")
    else:
        print("[信息] LLM 分析未启用，仅使用静态分析结果")

    return graph


def _group_by_language(files: list[Path]) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = {}
    for f in files:
        lang = SUPPORTED_EXTENSIONS.get(f.suffix.lower(), "unknown")
        grouped.setdefault(lang, []).append(f)
    return grouped


def generate_reports(graph: DependencyGraph, config: dict, project_root: str) -> dict:
    output_cfg = config.get("output", {})
    output_dir = output_cfg.get("dir", "./output")

    if not Path(output_dir).is_absolute():
        output_dir = str(Path(project_root) / output_dir)

    result: dict = {"output_dir": output_dir, "html": "", "json": "", "markdown": ""}

    output_format = output_cfg.get("format", "both")
    include_mermaid = output_cfg.get("include_mermaid", True)
    include_html = output_cfg.get("include_html", True)

    if output_format in ("json", "both"):
        path = JSONReporter().generate(graph, output_dir)
        result["json"] = path
        print(f"[输出] JSON 报告: {path}")

    if output_format in ("markdown", "both"):
        path = MarkdownReporter(include_mermaid=include_mermaid).generate(graph, output_dir)
        result["markdown"] = path
        print(f"[输出] Markdown 报告: {path}")

    if include_html:
        path = HTMLReporter().generate(graph, output_dir)
        result["html"] = path
        print(f"[输出] HTML 可视化报告: {path}")

    return result


def print_summary(graph: DependencyGraph) -> None:
    stats = graph.get_stats()
    print()
    print("=" * 50)
    print("  分析完成 - 项目摘要")
    print("=" * 50)
    print(f"  总文件数:   {stats['total_files']}")
    print(f"  总代码行:   {stats['total_lines']}")
    print(f"  总依赖关系: {stats['total_imports']}")
    print("=" * 50)


def print_rule_result(result: RuleResult) -> None:
    print(f"[信息] 校验规则: {result.checked_rules} 条, 通过: {result.passed_rules} 条")
    if result.violations:
        print(f"[警告] 发现 {len(result.violations)} 个违规 ({result.error_count} 错误, {result.warning_count} 警告)")
        for v in result.violations:
            tag = {
                "error": "[错误]",
                "warning": "[警告]",
                "info": "[建议]",
            }.get(v.severity, "[?]")
            detail = f"  {tag} [{v.rule_name}] {v.message}"
            if v.related_file:
                detail += f" -> {v.related_file}"
            print(detail)
    else:
        print("[通过] 所有规则校验通过")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="代码自动分析工具 - 梳理文件关系与功能",
    )
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="配置文件路径 (默认: config.yaml)",
    )
    parser.add_argument(
        "-d", "--dir",
        default=None,
        help="要分析的项目目录 (默认: 当前目录)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="禁用 LLM 分析，仅使用静态分析",
    )
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="禁用 HTML 可视化报告",
    )

    args = parser.parse_args()

    config = load_config(args.config)

    if args.no_llm:
        config.setdefault("llm", {})["enabled"] = False
    if args.no_html:
        config.setdefault("output", {})["include_html"] = False

    project_root = args.dir or config.get("analyzer", {}).get("target_dir", ".")
    if not Path(project_root).is_absolute():
        project_root = str(Path.cwd() / project_root)

    start_time = time.time()

    graph = run_analysis(config, project_root)
    generate_reports(graph, config, project_root)
    print_summary(graph)

    rules_cfg = config.get("rules", {})
    if rules_cfg.get("enabled", False) and rules_cfg.get("rules"):
        print("\n" + "=" * 50)
        print("  架构规则校验")
        print("=" * 50)
        engine = RuleEngine(rules_cfg)
        result = engine.validate(graph)
        print_rule_result(result)

    elapsed = time.time() - start_time
    print(f"\n[完成] 总耗时: {elapsed:.2f} 秒")


if __name__ == "__main__":
    main()