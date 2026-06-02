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

        return FileNode(
            path=str(abs_path),
            relative_path=str(abs_path.relative_to(self._project_root)).replace(os.sep, "/"),
            language=language,
            purpose=purpose,
            purpose_source="static",
            imports=imports,
            exports=exports,
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

    def _resolve_js_import(self, module_spec: str, source_dir: Path) -> Optional[str]:
        if module_spec.startswith("."):
            resolved = self._to_relative(source_dir / module_spec)
            if resolved:
                return resolved

            for ext in (".js", ".ts", ".jsx", ".tsx"):
                resolved = self._to_relative(source_dir / (module_spec + ext))
                if resolved:
                    return resolved

            for ext in (".js", ".ts", ".jsx", ".tsx"):
                resolved = self._to_relative(source_dir / module_spec / f"index{ext}")
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