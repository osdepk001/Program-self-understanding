from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from ..graph.dependency_graph import FileNode


class PHParser:
    """PHP 专用解析器：解析 namespace、use、类继承、接口、trait、函数调用等。"""

    # 注释
    COMMENT_RE = re.compile(
        r"//.*?$|#.*?$|/\*[\s\S]*?\*/",
        re.MULTILINE,
    )

    # 命名空间声明
    NAMESPACE_RE = re.compile(r"namespace\s+([\w\\]+)\s*;")

    # use 语句：use Foo\Bar\Baz;
    USE_SINGLE_RE = re.compile(r"use\s+([\w\\]+)\s*;")
    # use Foo\Bar\Baz as Alias;
    USE_AS_RE = re.compile(r"use\s+([\w\\]+)\s+as\s+(\w+)\s*;")
    # use Foo\Bar\{Baz, Qux};
    USE_GROUP_RE = re.compile(r"use\s+([\w\\]+)\\\{([^}]+)\}\s*;")

    # 类定义
    CLASS_RE = re.compile(
        r"(?:abstract\s+)?(?:final\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w\s,]+))?",
        re.MULTILINE,
    )
    # 接口定义
    INTERFACE_RE = re.compile(r"interface\s+(\w+)(?:\s+extends\s+([\w\s,]+))?")
    # trait 定义
    TRAIT_RE = re.compile(r"trait\s+(\w+)")

    # 类内部 trait use: use TraitA, TraitB;
    TRAIT_USE_RE = re.compile(
        r"(?<!\bnamespace\s)(?<!\buse\s)\buse\s+([\w\\, ]+)\s*;",
        re.MULTILINE,
    )

    # 函数定义
    FUNCTION_RE = re.compile(
        r"(?:public\s+|protected\s+|private\s+|static\s+|abstract\s+|final\s+)*"
        r"function\s+(\w+)\s*\(",
        re.MULTILINE,
    )

    # new 实例化
    NEW_RE = re.compile(r"new\s+(\w+)\s*\(")

    # 静态方法调用: ClassName::method()
    STATIC_CALL_RE = re.compile(r"(\w+)::(\w+)\s*\(")

    # 静态属性访问: ClassName::PROP
    STATIC_PROP_RE = re.compile(r"(\w+)::\$?(\w+)\b(?!\s*\()")

    # 箭头调用: $obj->method()
    ARROW_CALL_RE = re.compile(r"\$(\w+)\s*->\s*(\w+)\s*\(")

    # include/require
    INCLUDE_RE = re.compile(
        r"(?:include|require)(?:_once)?\s*\(?\s*[\"']([^\"']+)[\"']\s*\)?\s*;"
    )

    def __init__(self, project_root: str) -> None:
        self._project_root = Path(project_root).resolve()

    def parse_file(self, file_path: str) -> Optional[FileNode]:
        abs_path = Path(file_path).resolve()
        if not abs_path.exists():
            return None

        try:
            source_code = abs_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return None

        # 去掉注释
        cleaned = self.COMMENT_RE.sub("", source_code)

        # 提取命名空间
        namespace = self._extract_namespace(cleaned)
        source_dir = abs_path.parent

        imports = self._extract_imports(cleaned, source_dir, namespace)
        exports = self._extract_exports(cleaned)
        purpose = self._extract_purpose(cleaned)
        cross_refs, call_targets, unused_imports = self._extract_cross_refs_v2(
            cleaned, source_dir, namespace, imports
        )

        return FileNode(
            path=str(abs_path),
            relative_path=str(abs_path.relative_to(self._project_root)).replace(os.sep, "/"),
            language="php",
            purpose=purpose,
            purpose_source="static",
            imports=imports,
            exports=exports,
            cross_refs=cross_refs,
            call_targets=call_targets,
            unused_imports=unused_imports,
            lines=len(source_code.splitlines()),
        )

    def _extract_namespace(self, source: str) -> str:
        """提取命名空间声明。"""
        m = self.NAMESPACE_RE.search(source)
        if m:
            return m.group(1).strip("\\")
        return ""

    def _extract_imports(
        self, source: str, source_dir: Path, namespace: str
    ) -> list[str]:
        """提取所有依赖：use 语句 + include/require。"""
        imports: list[str] = []
        used_symbols: set[str] = set()

        # use 语句
        for match in self.USE_SINGLE_RE.finditer(source):
            full_name = match.group(1)
            resolved = self._resolve_use(full_name, source_dir)
            if resolved:
                imports.append(resolved)

        for match in self.USE_AS_RE.finditer(source):
            full_name = match.group(1)
            resolved = self._resolve_use(full_name, source_dir)
            if resolved:
                imports.append(resolved)

        for match in self.USE_GROUP_RE.finditer(source):
            prefix = match.group(1)
            group_str = match.group(2)
            for name in group_str.split(","):
                name = name.strip()
                if name:
                    full_name = f"{prefix}\\{name}"
                    resolved = self._resolve_use(full_name, source_dir)
                    if resolved:
                        imports.append(resolved)

        # include/require
        for match in self.INCLUDE_RE.finditer(source):
            included = match.group(1)
            resolved = self._resolve_include(included, source_dir)
            if resolved:
                imports.append(resolved)

        return sorted(set(imports))

    def _resolve_use(self, full_name: str, source_dir: Path) -> Optional[str]:
        """解析 use 语句中的命名空间引用到文件路径。"""
        ns_path = full_name.replace("\\", "/").lstrip("\\")
        class_name = full_name.split("\\")[-1]
        candidates = [
            self._project_root / f"{ns_path}.php",
            source_dir / f"{ns_path}.php",
        ]

        for candidate in candidates:
            try:
                resolved = candidate.resolve()
                if resolved.is_file():
                    return str(resolved.relative_to(self._project_root)).replace(os.sep, "/")
            except (ValueError, OSError):
                pass

        # 尝试向上遍历
        current = source_dir
        while current >= self._project_root:
            candidate = current / f"{ns_path}.php"
            try:
                resolved = candidate.resolve()
                if resolved.is_file():
                    return str(resolved.relative_to(self._project_root)).replace(os.sep, "/")
            except (ValueError, OSError):
                pass
            if current == self._project_root:
                break
            current = current.parent

        # 回退：按类名搜索整个项目
        found = self._search_by_class_name(class_name)
        if found:
            return found

        return None

    def _search_by_class_name(self, class_name: str) -> Optional[str]:
        """在项目根目录下按类名搜索 PHP 文件。"""
        for root, dirs, files in os.walk(str(self._project_root)):
            # 跳过 vendor、node_modules 等目录
            dirs[:] = [d for d in dirs if d not in ("vendor", "node_modules", ".git", "__pycache__")]
            target = f"{class_name}.php"
            if target in files:
                full_path = Path(root) / target
                try:
                    return str(full_path.relative_to(self._project_root)).replace(os.sep, "/")
                except ValueError:
                    pass
        return None

    def _resolve_include(self, included: str, source_dir: Path) -> Optional[str]:
        """解析 include/require 路径。"""
        candidates = [
            source_dir / included,
            self._project_root / included,
        ]
        if not included.endswith(".php"):
            candidates.extend([
                source_dir / f"{included}.php",
                self._project_root / f"{included}.php",
            ])

        for candidate in candidates:
            try:
                resolved = candidate.resolve()
                if resolved.is_file():
                    return str(resolved.relative_to(self._project_root)).replace(os.sep, "/")
            except (ValueError, OSError):
                pass

        return None

    def _extract_exports(self, source: str) -> list[str]:
        """提取导出：类、接口、trait、函数定义。"""
        exports: list[str] = []

        for match in self.CLASS_RE.finditer(source):
            name = match.group(1)
            if not name.startswith("_"):
                exports.append(f"class:{name}")

        for match in self.INTERFACE_RE.finditer(source):
            name = match.group(1)
            if not name.startswith("_"):
                exports.append(f"interface:{name}")

        for match in self.TRAIT_RE.finditer(source):
            name = match.group(1)
            if not name.startswith("_"):
                exports.append(f"trait:{name}")

        for match in self.FUNCTION_RE.finditer(source):
            name = match.group(1)
            if not name.startswith("_"):
                exports.append(f"fn:{name}")

        return exports

    def _extract_purpose(self, source: str) -> str:
        """提取文件功能描述。"""
        classes = [m.group(1) for m in self.CLASS_RE.finditer(source)]
        interfaces = [m.group(1) for m in self.INTERFACE_RE.finditer(source)]
        traits = [m.group(1) for m in self.TRAIT_RE.finditer(source)]
        functions = [m.group(1) for m in self.FUNCTION_RE.finditer(source)]

        if classes:
            names = ", ".join(classes[:3])
            suffix = " ..." if len(classes) > 3 else ""
            return f"定义类: {names}{suffix}"
        if interfaces:
            names = ", ".join(interfaces[:3])
            suffix = " ..." if len(interfaces) > 3 else ""
            return f"定义接口: {names}{suffix}"
        if traits:
            names = ", ".join(traits[:3])
            suffix = " ..." if len(traits) > 3 else ""
            return f"定义 Trait: {names}{suffix}"
        if functions:
            names = ", ".join(functions[:3])
            suffix = " ..." if len(functions) > 3 else ""
            return f"定义函数: {names}{suffix}"

        return "PHP 文件"

    def _extract_cross_refs_v2(
        self, source: str, source_dir: Path, namespace: str, imports: list[str]
    ) -> tuple[dict[str, list[str]], list[dict], list[str]]:
        """V2 深度分析：符号引用 + 调用目标 + 未使用导入。"""
        cross_refs: dict[str, list[str]] = {}
        call_targets: list[dict] = []
        all_imported: set[str] = set(imports)

        # Step 1: 建立 use 语句的符号到模块映射
        # 收集本文件定义的类/接口/trait 名称（用于排除自引用）
        local_defs: set[str] = set()
        for m in self.CLASS_RE.finditer(source):
            local_defs.add(m.group(1))
        for m in self.INTERFACE_RE.finditer(source):
            local_defs.add(m.group(1))
        for m in self.TRAIT_RE.finditer(source):
            local_defs.add(m.group(1))

        symbol_to_module: dict[str, str] = {}

        # use Foo\Bar\Baz;
        for match in self.USE_SINGLE_RE.finditer(source):
            full_name = match.group(1)
            class_name = full_name.split("\\")[-1]
            resolved = self._resolve_use(full_name, source_dir)
            if resolved:
                symbol_to_module[class_name] = resolved

        # use Foo\Bar\Baz as Alias;
        for match in self.USE_AS_RE.finditer(source):
            full_name = match.group(1)
            alias = match.group(2)
            resolved = self._resolve_use(full_name, source_dir)
            if resolved:
                symbol_to_module[alias] = resolved

        # use Foo\Bar\{Baz, Qux};
        for match in self.USE_GROUP_RE.finditer(source):
            prefix = match.group(1)
            group_str = match.group(2)
            for name in group_str.split(","):
                name = name.strip()
                if name:
                    full_name = f"{prefix}\\{name}"
                    resolved = self._resolve_use(full_name, source_dir)
                    if resolved:
                        symbol_to_module[name] = resolved

        if not symbol_to_module:
            return cross_refs, call_targets, []

        # 移除本地定义的符号（避免自引用）
        symbol_to_module = {
            k: v for k, v in symbol_to_module.items() if k not in local_defs
        }

        # Step 2: 检查符号使用 + 构建 call_targets
        lines = source.split("\n")
        exclude_line = re.compile(
            r"^\s*(?:use\s|namespace\s|include|require)"
        )

        for symbol, resolved_path in symbol_to_module.items():
            usage_pattern = re.compile(r"\b" + re.escape(symbol) + r"\b")
            found = False
            for line in lines:
                if not exclude_line.match(line):
                    if usage_pattern.search(line):
                        found = True
                        break

            if not found:
                continue

            if resolved_path not in cross_refs:
                cross_refs[resolved_path] = []
            if symbol not in cross_refs[resolved_path]:
                cross_refs[resolved_path].append(symbol)

            # 追踪 new Symbol(...)
            for match in self.NEW_RE.finditer(source):
                if match.group(1) == symbol:
                    call_targets.append({
                        "file": resolved_path,
                        "symbol": symbol,
                        "kind": "instantiate",
                        "context": f"new {symbol}()",
                    })

            # 追踪 Symbol::method(...)
            static_call_pattern = re.compile(
                r"\b" + re.escape(symbol) + r"::(\w+)\s*\(",
                re.MULTILINE,
            )
            for match in static_call_pattern.finditer(source):
                method_name = match.group(1)
                call_targets.append({
                    "file": resolved_path,
                    "symbol": method_name,
                    "kind": "static_call",
                    "context": f"{symbol}::{method_name}()",
                })

            # 追踪 Symbol::PROP
            static_prop_pattern = re.compile(
                r"\b" + re.escape(symbol) + r"::\$?(\w+)(?!\s*\()",
                re.MULTILINE,
            )
            for match in static_prop_pattern.finditer(source):
                prop_name = match.group(1)
                if any(
                    c["symbol"] == prop_name and c["file"] == resolved_path
                    for c in call_targets
                ):
                    continue
                call_targets.append({
                    "file": resolved_path,
                    "symbol": prop_name,
                    "kind": "static_prop",
                    "context": f"{symbol}::${prop_name}",
                })

            # 追踪 Symbol 作为 extends/implements
            extends_pattern = re.compile(
                r"extends\s+" + re.escape(symbol) + r"\b",
                re.MULTILINE,
            )
            for match in extends_pattern.finditer(source):
                call_targets.append({
                    "file": resolved_path,
                    "symbol": symbol,
                    "kind": "extends",
                    "context": f"extends {symbol}",
                })

            implements_pattern = re.compile(
                r"implements\s+[\w\s,]*\b" + re.escape(symbol) + r"\b",
                re.MULTILINE,
            )
            for match in implements_pattern.finditer(source):
                call_targets.append({
                    "file": resolved_path,
                    "symbol": symbol,
                    "kind": "implements",
                    "context": f"implements {symbol}",
                })

            # 追踪类内部 trait use: use TraitName;
            trait_use_pattern = re.compile(
                r"^\s*use\s+[\w\\, ]*\b" + re.escape(symbol) + r"\b[\w\\, ]*;",
                re.MULTILINE,
            )
            for match in trait_use_pattern.finditer(source):
                # 排除命名空间级别的 use 语句（包含 \ 的）
                matched = match.group(0)
                if "\\" in matched:
                    continue
                call_targets.append({
                    "file": resolved_path,
                    "symbol": symbol,
                    "kind": "trait_use",
                    "context": f"use {symbol}",
                })

        # Step 3: 检测未使用的导入
        used_modules: set[str] = set(cross_refs.keys())
        unused_imports = sorted(all_imported - used_modules)

        return cross_refs, call_targets, unused_imports