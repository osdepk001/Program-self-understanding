"""
代码质量分析器：计算圈复杂度、函数长度、注释率、空行率等指标。
"""
from __future__ import annotations

import re
import math
from pathlib import Path
from typing import Any
from collections import Counter


class FunctionInfo:
    def __init__(self, name: str, file_path: str, line: int, end_line: int,
                 complexity: int = 0, lines: int = 0):
        self.name = name
        self.file_path = file_path
        self.line = line
        self.end_line = end_line
        self.complexity = complexity
        self.lines = lines

    def to_dict(self) -> dict:
        return {
            "name": self.name, "file": self.file_path,
            "line": self.line, "end_line": self.end_line,
            "complexity": self.complexity, "lines": self.lines,
        }


class FileQuality:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.total_lines = 0
        self.code_lines = 0
        self.comment_lines = 0
        self.blank_lines = 0
        self.functions: list[FunctionInfo] = []
        self.complexity = 0
        self.language = ""

    @property
    def comment_ratio(self) -> float:
        return self.comment_lines / max(self.total_lines, 1)

    @property
    def blank_ratio(self) -> float:
        return self.blank_lines / max(self.total_lines, 1)

    @property
    def avg_function_length(self) -> float:
        if not self.functions:
            return 0
        return sum(f.lines for f in self.functions) / len(self.functions)

    @property
    def max_complexity(self) -> int:
        if not self.functions:
            return 0
        return max(f.complexity for f in self.functions)

    def to_dict(self) -> dict:
        return {
            "file": self.file_path,
            "language": self.language,
            "total_lines": self.total_lines,
            "code_lines": self.code_lines,
            "comment_lines": self.comment_lines,
            "blank_lines": self.blank_lines,
            "comment_ratio": round(self.comment_ratio, 3),
            "blank_ratio": round(self.blank_ratio, 3),
            "function_count": len(self.functions),
            "avg_function_length": round(self.avg_function_length, 1),
            "total_complexity": self.complexity,
            "max_complexity": self.max_complexity,
            "complex_functions": [f.to_dict() for f in self.functions if f.complexity > 10],
        }


class QualityAnalyzer:
    """代码质量分析器。"""

    # 复杂度阈值
    COMPLEXITY_HIGH = 15
    COMPLEXITY_WARN = 10
    FUNCTION_LENGTH_HIGH = 50
    COMMENT_RATIO_LOW = 0.05

    def __init__(self):
        self._files: list[FileQuality] = []
        self._all_functions: list[FunctionInfo] = []

    def analyze(self, files: list[Path]) -> list[FileQuality]:
        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            fq = FileQuality(str(file_path))
            fq.language = file_path.suffix.lower()

            # 统计行数
            lines = content.split("\n")
            fq.total_lines = len(lines)

            # 找函数
            self._find_functions(file_path, content, fq)

            # 统计注释行
            fq.comment_lines = self._count_comment_lines(content, fq.language)
            fq.blank_lines = content.count("\n\n")  # 近似空行
            fq.code_lines = fq.total_lines - fq.comment_lines - fq.blank_lines

            # 计算复杂度
            fq.complexity = sum(f.complexity for f in fq.functions)

            self._files.append(fq)
            self._all_functions.extend(fq.functions)

        return self._files

    def _find_functions(self, file_path: Path, content: str, fq: FileQuality) -> None:
        ext = file_path.suffix.lower()
        if ext in (".py",):
            self._find_python_functions(file_path, content, fq)
        elif ext in (".java",):
            self._find_java_functions(file_path, content, fq)
        elif ext in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
            self._find_js_functions(file_path, content, fq)
        elif ext in (".go",):
            self._find_go_functions(file_path, content, fq)
        elif ext in (".php",):
            self._find_php_functions(file_path, content, fq)
        elif ext in (".rb",):
            self._find_ruby_functions(file_path, content, fq)
        elif ext in (".cs",):
            self._find_csharp_functions(file_path, content, fq)

    def _find_python_functions(self, file_path: Path, content: str, fq: FileQuality) -> None:
        for m in re.finditer(r'(?:^|\n)(\s*)(?:async\s+)?def\s+(\w+)\s*\(', content):
            start_line = content[:m.start()].count("\n") + 1
            name = m.group(2)
            indent = len(m.group(1))
            end_line = self._find_python_block_end(content, m.start(), indent)
            lines = end_line - start_line + 1
            complexity = self._calc_complexity(content, m.start(), content.find("\n", m.end()) + 1)

            fi = FunctionInfo(name=name, file_path=str(file_path),
                              line=start_line, end_line=end_line,
                              complexity=complexity, lines=lines)
            fq.functions.append(fi)

    def _find_java_functions(self, file_path: Path, content: str, fq: FileQuality) -> None:
        """查找 Java 方法。"""
        for m in re.finditer(
            r'(?:public|private|protected|static|final|abstract|synchronized|native)?\s*'
            r'(?:[\w<>[\],\s]+)\s+(\w+)\s*\(([^)]*)\)\s*\{',
            content
        ):
            start_line = content[:m.start()].count("\n") + 1
            name = m.group(1)
            params = m.group(2)
            # 跳过 getter/setter 和简单方法
            if name in ("toString", "equals", "hashCode", "clone"):
                continue
            if name.startswith("get") and len(params.strip()) == 0:
                continue
            if name.startswith("set") and params.count(",") == 0:
                continue

            end_line = content[:m.end()].count("\n") + 1
            body_end = self._find_brace_end(content, m.end() - 1)
            if body_end > 0:
                end_line = content[:body_end].count("\n") + 1
            lines = end_line - start_line + 1
            complexity = self._calc_complexity(content, m.start(), m.end())

            fi = FunctionInfo(name=name, file_path=str(file_path),
                              line=start_line, end_line=end_line,
                              complexity=complexity, lines=lines)
            fq.functions.append(fi)

    def _find_js_functions(self, file_path: Path, content: str, fq: FileQuality) -> None:
        for m in re.finditer(r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\s*\([^)]*\)\s*=>)', content):
            name = m.group(1) or m.group(2) or "anonymous"
            start_line = content[:m.start()].count("\n") + 1
            complexity = self._calc_complexity(content, m.start(), m.end())
            lines = max(1, complexity * 2)  # 近似

            fq.functions.append(FunctionInfo(
                name=name, file_path=str(file_path),
                line=start_line, end_line=start_line + lines,
                complexity=complexity, lines=lines,
            ))

    def _find_go_functions(self, file_path: Path, content: str, fq: FileQuality) -> None:
        for m in re.finditer(r'func\s+(?:\([^)]*\)\s+)?(\w+)\s*\(', content):
            name = m.group(1)
            start_line = content[:m.start()].count("\n") + 1
            complexity = self._calc_complexity(content, m.start(), m.end())
            lines = max(1, complexity * 2)

            fq.functions.append(FunctionInfo(
                name=name, file_path=str(file_path),
                line=start_line, end_line=start_line + lines,
                complexity=complexity, lines=lines,
            ))

    def _find_php_functions(self, file_path: Path, content: str, fq: FileQuality) -> None:
        for m in re.finditer(r'function\s+(\w+)\s*\(', content):
            name = m.group(1)
            start_line = content[:m.start()].count("\n") + 1
            complexity = self._calc_complexity(content, m.start(), m.end())
            lines = max(1, complexity * 2)

            fq.functions.append(FunctionInfo(
                name=name, file_path=str(file_path),
                line=start_line, end_line=start_line + lines,
                complexity=complexity, lines=lines,
            ))

    def _find_ruby_functions(self, file_path: Path, content: str, fq: FileQuality) -> None:
        for m in re.finditer(r'(?:^\s*)?def\s+(\w+)', content, re.MULTILINE):
            name = m.group(1)
            start_line = content[:m.start()].count("\n") + 1
            complexity = max(1, content[m.start():m.start() + 500].count("if ") +
                           content[m.start():m.start() + 500].count("while ") +
                           content[m.start():m.start() + 500].count("case "))

            fq.functions.append(FunctionInfo(
                name=name, file_path=str(file_path),
                line=start_line, end_line=start_line + complexity * 2,
                complexity=complexity, lines=complexity * 2,
            ))

    def _find_csharp_functions(self, file_path: Path, content: str, fq: FileQuality) -> None:
        for m in re.finditer(
            r'(?:public|private|protected|internal|static|virtual|override|async|abstract)?\s*'
            r'(?:[\w<>[\],\s]+)\s+(\w+)\s*\(([^)]*)\)\s*\{',
            content
        ):
            name = m.group(1)
            if name in ("ToString", "Equals", "GetHashCode", "Dispose"):
                continue
            start_line = content[:m.start()].count("\n") + 1
            complexity = self._calc_complexity(content, m.start(), m.end())
            lines = max(1, complexity * 2)

            fq.functions.append(FunctionInfo(
                name=name, file_path=str(file_path),
                line=start_line, end_line=start_line + lines,
                complexity=complexity, lines=lines,
            ))

    @staticmethod
    def _calc_complexity(content: str, start: int, end: int) -> int:
        """计算圈复杂度（McCabe 复杂度）。"""
        chunk = content[start:start + 2000]  # 只看前 2000 字符
        complexity = 1  # 基础复杂度

        # 分支关键词
        for keyword in ("if ", "elif ", "else if", "for ", "while ", "case ",
                        "catch ", "&&", "||", "? ", "??"):
            complexity += chunk.count(keyword)

        # 循环中的 break/continue 不算额外分支
        # 但 and/or 在 Python 中算分支
        complexity += chunk.count(" and ") + chunk.count(" or ")

        return min(complexity, 100)  # 上限

    @staticmethod
    def _count_comment_lines(content: str, ext: str) -> int:
        """统计注释行数。"""
        count = 0
        lines = content.split("\n")

        if ext in (".py", ".rb", ".sh", ".yml", ".yaml", ".toml", ".cfg"):
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("#"):
                    count += 1
        elif ext in (".java", ".js", ".jsx", ".ts", ".tsx", ".go", ".cs", ".swift", ".kt", ".scala", ".cpp", ".c", ".h", ".php"):
            in_block = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("//"):
                    count += 1
                elif stripped.startswith("/*"):
                    in_block = True
                    count += 1
                elif "*/" in stripped:
                    in_block = False
                    count += 1
                elif in_block:
                    count += 1
        elif ext in (".sql",):
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("--"):
                    count += 1

        return count

    @staticmethod
    def _find_python_block_end(content: str, start: int, base_indent: int) -> int:
        """找到 Python 代码块结束行。"""
        lines = content[start:].split("\n")
        line_num = content[:start].count("\n") + 1
        if len(lines) < 2:
            return line_num

        for i, line in enumerate(lines[1:], 1):
            stripped = line.strip()
            if stripped == "" or stripped.startswith("#"):
                continue
            if len(line) - len(line.lstrip()) <= base_indent and (
                not stripped.startswith((")","]","}")) and
                not stripped.startswith(".") and
                not stripped.startswith(",")
            ):
                return line_num + i - 1
        return line_num + len(lines) - 1

    @staticmethod
    def _find_brace_end(content: str, start: int) -> int:
        depth = 0
        for i in range(start, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
                if depth == 0:
                    return i
        return -1


def build_quality_summary(files: list[FileQuality]) -> dict[str, Any]:
    """构建质量分析汇总。"""
    if not files:
        return {}

    total_lines = sum(f.total_lines for f in files)
    total_code = sum(f.code_lines for f in files)
    total_comments = sum(f.comment_lines for f in files)
    total_blank = sum(f.blank_lines for f in files)
    all_funcs = sum(len(f.functions) for f in files)
    total_complexity = sum(f.complexity for f in files)

    # 复杂函数（复杂度 > 10）
    complex_funcs = []
    for fq in files:
        for func in fq.functions:
            if func.complexity >= QualityAnalyzer.COMPLEXITY_WARN:
                complex_funcs.append(func.to_dict())
    complex_funcs.sort(key=lambda x: x["complexity"], reverse=True)
    complex_funcs = complex_funcs[:20]

    # 文件级评分
    quality_grade = "A"
    avg_comment = total_comments / max(total_lines, 1)
    if avg_comment < 0.03:
        quality_grade = "C"
    elif avg_comment < 0.08:
        quality_grade = "B"

    if total_complexity / max(all_funcs, 1) > 15:
        quality_grade = "C" if quality_grade == "B" else "D"

    return {
        "grade": quality_grade,
        "total_lines": total_lines,
        "code_lines": total_code,
        "comment_lines": total_comments,
        "blank_lines": total_blank,
        "comment_ratio": round(total_comments / max(total_lines, 1), 3),
        "function_count": all_funcs,
        "total_complexity": total_complexity,
        "avg_complexity": round(total_complexity / max(all_funcs, 1), 1),
        "complex_functions": complex_funcs,
        "files": [f.to_dict() for f in files[:50]],  # 仅前 50
    }