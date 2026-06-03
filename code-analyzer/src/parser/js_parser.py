from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from ..graph.dependency_graph import FileNode


class JSParser:
    """通过正则表达式解析 JavaScript/TypeScript 文件的导入、导出和功能。"""

    IMPORT_RE = re.compile(
        r"(?:import|export)\s+(?:type\s+)?(?:(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)\s*,?\s*)*"
        r"(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)?\s*"
        r"from\s+['\"]([^'\"]+)['\"]",
        re.MULTILINE,
    )

    SIDE_EFFECT_IMPORT_RE = re.compile(
        r"import\s+['\"]([^'\"]+)['\"]",
        re.MULTILINE,
    )

    REQUIRE_RE = re.compile(
        r"(?:const|let|var)\s+(?:\{[^}]*\}|\w+)\s*=\s*require\s*\(\s*['\"]([^'\"]+)['\"]",
        re.MULTILINE,
    )

    DYNAMIC_IMPORT_RE = re.compile(
        r"import\s*\(\s*['\"]([^'\"]+)['\"]",
        re.MULTILINE,
    )

    EXPORT_CLASS_RE = re.compile(r"export\s+(?:default\s+)?class\s+(\w+)", re.MULTILINE)
    EXPORT_FN_RE = re.compile(r"export\s+(?:default\s+)?(?:async\s+)?function\s+(\w+)", re.MULTILINE)
    EXPORT_CONST_RE = re.compile(r"export\s+(?:const|let|var)\s+(\w+)", re.MULTILINE)
    EXPORT_DEFAULT_RE = re.compile(r"export\s+default\s+(\w+)", re.MULTILINE)

    COMMENT_RE = re.compile(r"//.*$|/\*[\s\S]*?\*/", re.MULTILINE)

    NAMED_IMPORT_RE = re.compile(
        r"import\s+\{([^}]+)\}\s*from\s+['\"]([^'\"]+)['\"]",
        re.MULTILINE,
    )
    STAR_IMPORT_RE = re.compile(
        r"import\s+\*\s+as\s+(\w+)\s*from\s+['\"]([^'\"]+)['\"]",
        re.MULTILINE,
    )
    DEFAULT_IMPORT_RE = re.compile(
        r"import\s+(\w+)\s*from\s+['\"]([^'\"]+)['\"]",
        re.MULTILINE,
    )
    REQUIRE_NAMED_RE = re.compile(
        r"(?:const|let|var)\s+\{([^}]+)\}\s*=\s*require\s*\(\s*['\"]([^'\"]+)['\"]",
        re.MULTILINE,
    )
    REQUIRE_DEFAULT_RE = re.compile(
        r"(?:const|let|var)\s+(\w+)\s*=\s*require\s*\(\s*['\"]([^'\"]+)['\"]",
        re.MULTILINE,
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

        ext = abs_path.suffix.lower()
        language = "typescript" if ext in (".ts", ".tsx") else "javascript"

        cleaned = self.COMMENT_RE.sub("", source_code)

        imports = self._extract_imports(cleaned, abs_path)
        exports = self._extract_exports(cleaned)
        purpose = self._extract_purpose(cleaned)
        cross_refs = self._extract_cross_refs(cleaned, abs_path)

        return FileNode(
            path=str(abs_path),
            relative_path=str(abs_path.relative_to(self._project_root)).replace(os.sep, "/"),
            language=language,
            purpose=purpose,
            purpose_source="static",
            imports=imports,
            exports=exports,
            cross_refs=cross_refs,
            lines=len(source_code.splitlines()),
        )

    def _extract_imports(self, source: str, source_path: Path) -> list[str]:
        imports: list[str] = []
        source_dir = source_path.parent

        patterns = [self.IMPORT_RE, self.SIDE_EFFECT_IMPORT_RE, self.REQUIRE_RE, self.DYNAMIC_IMPORT_RE]

        for pattern in patterns:
            for match in pattern.finditer(source):
                module_spec = match.group(1)
                resolved = self._resolve_js_import(module_spec, source_dir)
                if resolved:
                    imports.append(resolved)

        return sorted(set(imports))

    def _extract_cross_refs(self, source: str, source_path: Path) -> dict[str, list[str]]:
        """提取跨文件符号引用：追踪 JS/TS import 的符号在代码中是否被实际使用。"""
        cross_refs: dict[str, list[str]] = {}
        source_dir = source_path.parent

        # symbol_name -> resolved_relative_path
        symbol_to_module: dict[str, str] = {}

        # 处理 named imports: import { A, B } from './x'
        for match in self.NAMED_IMPORT_RE.finditer(source):
            names_str = match.group(1)
            module_spec = match.group(2)
            resolved = self._resolve_js_import(module_spec, source_dir)
            if resolved:
                for name_part in names_str.split(","):
                    name_part = name_part.strip()
                    if " as " in name_part:
                        _, alias = name_part.split(" as ", 1)
                        symbol_to_module[alias.strip()] = resolved
                    else:
                        symbol_to_module[name_part] = resolved

        # 处理 star imports: import * as X from './x'
        for match in self.STAR_IMPORT_RE.finditer(source):
            name = match.group(1)
            module_spec = match.group(2)
            resolved = self._resolve_js_import(module_spec, source_dir)
            if resolved:
                symbol_to_module[name] = resolved

        # 处理 default imports: import X from './x'
        for match in self.DEFAULT_IMPORT_RE.finditer(source):
            name = match.group(1)
            module_spec = match.group(2)
            resolved = self._resolve_js_import(module_spec, source_dir)
            if resolved:
                symbol_to_module[name] = resolved

        # 处理 require named: const { A, B } = require('./x')
        for match in self.REQUIRE_NAMED_RE.finditer(source):
            names_str = match.group(1)
            module_spec = match.group(2)
            resolved = self._resolve_js_import(module_spec, source_dir)
            if resolved:
                for name_part in names_str.split(","):
                    name_part = name_part.strip()
                    if ":" in name_part:
                        orig, _ = name_part.split(":", 1)
                        symbol_to_module[orig.strip()] = resolved
                    elif " as " in name_part:
                        _, alias = name_part.split(" as ", 1)
                        symbol_to_module[alias.strip()] = resolved
                    else:
                        symbol_to_module[name_part] = resolved

        # 处理 require default: const X = require('./x')
        for match in self.REQUIRE_DEFAULT_RE.finditer(source):
            name = match.group(1)
            module_spec = match.group(2)
            resolved = self._resolve_js_import(module_spec, source_dir)
            if resolved:
                symbol_to_module[name] = resolved

        if not symbol_to_module:
            return cross_refs

        # Step 2: 在代码中查找符号使用
        for symbol, resolved_path in symbol_to_module.items():
            # 使用单词边界检查确保是独立标识符使用
            # 排除 import/require 语句行本身
            usage_pattern = re.compile(r'\b' + re.escape(symbol) + r'\b')
            # 在所有非 import 行中查找
            lines = source.split("\n")
            found = False
            for line in lines:
                if not re.match(r'^\s*(?:import|export|const|let|var)\s', line):
                    if usage_pattern.search(line):
                        found = True
                        break
            if found:
                if resolved_path not in cross_refs:
                    cross_refs[resolved_path] = []
                if symbol not in cross_refs[resolved_path]:
                    cross_refs[resolved_path].append(symbol)

        return cross_refs

    def _resolve_js_import(self, module_spec: str, source_dir: Path) -> Optional[str]:
        if module_spec.startswith("."):
            search_dirs = [source_dir, self._project_root]
            for search_dir in search_dirs:
                resolved = self._to_relative(search_dir / module_spec)
                if resolved:
                    return resolved

                for ext in (".js", ".ts", ".jsx", ".tsx"):
                    resolved = self._to_relative(search_dir / (module_spec + ext))
                    if resolved:
                        return resolved

                for ext in (".js", ".ts", ".jsx", ".tsx"):
                    resolved = self._to_relative(search_dir / module_spec / f"index{ext}")
                    if resolved:
                        return resolved

        return None

    def _to_relative(self, candidate: Path) -> Optional[str]:
        try:
            resolved = candidate.resolve()
            if resolved.is_file():
                return str(resolved.relative_to(self._project_root)).replace(os.sep, "/")
        except (ValueError, OSError):
            pass
        return None

    def _extract_exports(self, source: str) -> list[str]:
        exports: list[str] = []

        for match in self.EXPORT_CLASS_RE.finditer(source):
            name = match.group(1)
            if not name.startswith("_"):
                exports.append(f"class:{name}")

        for match in self.EXPORT_FN_RE.finditer(source):
            name = match.group(1)
            if not name.startswith("_"):
                exports.append(f"fn:{name}")

        for match in self.EXPORT_CONST_RE.finditer(source):
            name = match.group(1)
            if not name.startswith("_"):
                exports.append(f"var:{name}")

        for match in self.EXPORT_DEFAULT_RE.finditer(source):
            exports.append(f"default:{match.group(1)}")

        return exports

    def _extract_purpose(self, source: str) -> str:
        classes = self.EXPORT_CLASS_RE.findall(source)
        classes = [c for c in classes if not c.startswith("_")]
        functions = self.EXPORT_FN_RE.findall(source)
        functions = [f for f in functions if not f.startswith("_")]

        components = self._find_react_components(source)

        if components:
            names = ", ".join(components[:3])
            suffix = " ..." if len(components) > 3 else ""
            return f"React 组件: {names}{suffix}"

        if classes:
            names = ", ".join(classes[:3])
            suffix = " ..." if len(classes) > 3 else ""
            return f"定义类: {names}{suffix}"

        if functions:
            names = ", ".join(functions[:3])
            suffix = " ..." if len(functions) > 3 else ""
            return f"定义函数: {names}{suffix}"

        return "模块文件"

    def _find_react_components(self, source: str) -> list[str]:
        component_pattern = re.compile(
            r"(?:export\s+(?:default\s+)?(?:function|const|class)\s+)([A-Z]\w*)",
            re.MULTILINE,
        )
        return component_pattern.findall(source)