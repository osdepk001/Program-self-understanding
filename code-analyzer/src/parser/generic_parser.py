from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from ..graph.dependency_graph import FileNode


LANG_CONFIG = {
    "go": {
        "extensions": {".go"},
        "single_import": re.compile(r'import\s+(?:\w+\s+)?\"([^\"]+)\"'),
        "multi_import": re.compile(r'import\s*\(\s*((?:\s*(?:\w+\s+)?\"[^\"]+\"\s*)+)\s*\)'),
        "inner_import": re.compile(r'(?:\w+\s+)?\"([^\"]+)\"'),
    },
    "rust": {
        "extensions": {".rs"},
        "use_import": re.compile(r'use\s+((?:crate|self|super)(?:::\w+)*)(?:::[\{\*][^;]*)?;'),
        "mod_decl": re.compile(r'(?:pub\s+)?mod\s+(\w+)\s*;'),
        "extern_crate": re.compile(r'extern\s+crate\s+(\w+)\s*;'),
    },
    "java": {
        "extensions": {".java"},
        "import_single": re.compile(r'import\s+((?:static\s+)?[\w.]+(?:\.[A-Z]\w*)*)\s*;'),
        "package_decl": re.compile(r'package\s+([\w.]+)\s*;'),
    },
}

LANG_EXPORT_PATTERNS = {
    "go": [
        (re.compile(r'func\s+([A-Z]\w*)\s*\('), "fn"),
        (re.compile(r'type\s+([A-Z]\w*)\s+struct\s*\{'), "class"),
        (re.compile(r'type\s+([A-Z]\w*)\s+interface\s*\{'), "class"),
    ],
    "rust": [
        (re.compile(r'pub\s+fn\s+(\w+)\s*\('), "fn"),
        (re.compile(r'pub\s+struct\s+(\w+)'), "class"),
        (re.compile(r'pub\s+enum\s+(\w+)'), "class"),
        (re.compile(r'pub\s+trait\s+(\w+)'), "class"),
        (re.compile(r'pub\s+mod\s+(\w+)'), "mod"),
    ],
    "java": [
        (re.compile(r'public\s+(?:abstract\s+)?(?:static\s+)?class\s+(\w+)'), "class"),
        (re.compile(r'public\s+(?:static\s+)?interface\s+(\w+)'), "class"),
        (re.compile(r'public\s+(?:static\s+)?\w+(?:<[^>]+>)?\s+(\w+)\s*\('), "fn"),
    ],
}

COMMENT_PATTERN = re.compile(r'//.*$|/\*[\s\S]*?\*/', re.MULTILINE)


class GenericParser:
    """基于正则表达式的多语言解析器，支持 Go、Rust、Java。"""

    def __init__(self, project_root: str) -> None:
        self._project_root = Path(project_root).resolve()

    def parse_file(self, file_path: str, lang: str) -> Optional[FileNode]:
        abs_path = Path(file_path).resolve()
        if not abs_path.exists() or lang not in LANG_CONFIG:
            return None

        try:
            source_code = abs_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return None

        config = LANG_CONFIG[lang]
        cleaned = COMMENT_PATTERN.sub("", source_code)

        imports = self._extract_imports(cleaned, lang, config, abs_path)
        exports = self._extract_exports(cleaned, lang)
        purpose = self._extract_purpose(cleaned, lang)

        return FileNode(
            path=str(abs_path),
            relative_path=str(abs_path.relative_to(self._project_root)).replace(os.sep, "/"),
            language=lang,
            purpose=purpose,
            purpose_source="static",
            imports=imports,
            exports=exports,
            lines=len(source_code.splitlines()),
        )

    def _extract_imports(self, source: str, lang: str, config: dict, source_path: Path) -> list[str]:
        imports: list[str] = []

        if lang == "go":
            for match in config["single_import"].finditer(source):
                module = match.group(1)
                resolved = self._resolve_go_import(module, source_path)
                if resolved:
                    imports.append(resolved)

            for match in config["multi_import"].finditer(source):
                block = match.group(1)
                for inner in config["inner_import"].finditer(block):
                    module = inner.group(1)
                    if not module.startswith('"'):
                        resolved = self._resolve_go_import(module, source_path)
                        if resolved:
                            imports.append(resolved)

        elif lang == "rust":
            for match in config["use_import"].finditer(source):
                module_path = match.group(1)
                resolved = self._resolve_rust_import(module_path, source_path)
                if resolved:
                    imports.append(resolved)

            for match in config["mod_decl"].finditer(source):
                module_name = match.group(1)
                candidate = self._project_root / source_path.parent.relative_to(self._project_root) / f"{module_name}.rs"
                resolved = self._to_relative(candidate)
                if resolved:
                    imports.append(resolved)
                candidate = self._project_root / source_path.parent.relative_to(self._project_root) / module_name / "mod.rs"
                if candidate.exists():
                    resolved = self._to_relative(candidate)
                    if resolved:
                        imports.append(resolved)

        elif lang == "java":
            for match in config["import_single"].finditer(source):
                module = match.group(1)
                resolved = self._resolve_java_import(module, source_path)
                if resolved:
                    imports.append(resolved)

        return sorted(set(imports))

    def _resolve_go_import(self, module: str, source_path: Path) -> Optional[str]:
        parts = module.split("/")
        candidates = [
            self._project_root / "/".join(parts),
            self._project_root / f"{'/'.join(parts)}.go",
        ]
        for candidate in candidates:
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved
        return None

    def _resolve_rust_import(self, module: str, source_path: Path) -> Optional[str]:
        if module.startswith("crate::"):
            relative = module[6:].replace("::", "/")
        elif module.startswith("self::"):
            relative = module[5:].replace("::", "/")
        elif module.startswith("super::"):
            parts = module.split("::")
            depth = sum(1 for p in parts if p == "super")
            remaining = "/".join(parts[depth:]) if len(parts) > depth else ""
            current = source_path.parent
            for _ in range(depth):
                current = current.parent
            relative = str(current.relative_to(self._project_root)).replace(os.sep, "/")
            if remaining:
                relative += "/" + remaining
        else:
            return None

        candidates = [self._project_root / (relative + ".rs"), self._project_root / relative / "mod.rs"]
        for candidate in candidates:
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved
        return None

    def _resolve_java_import(self, module: str, source_path: Path) -> Optional[str]:
        if module.startswith("static "):
            module = module[7:]
        parts = module.split(".")
        for depth in range(len(parts), 0, -1):
            candidate = self._project_root / f"{'/'.join(parts[:depth])}.java"
            resolved = self._to_relative(candidate)
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

    def _extract_exports(self, source: str, lang: str) -> list[str]:
        exports: list[str] = []
        patterns = LANG_EXPORT_PATTERNS.get(lang, [])
        for pattern, kind in patterns:
            for match in pattern.finditer(source):
                name = match.group(1)
                if not name.startswith("_"):
                    exports.append(f"{kind}:{name}")
        return exports

    def _extract_purpose(self, source: str, lang: str) -> str:
        patterns = LANG_EXPORT_PATTERNS.get(lang, [])

        classes = []
        functions = []
        for pattern, kind in patterns:
            for match in pattern.finditer(source):
                name = match.group(1)
                if name.startswith("_"):
                    continue
                if kind in ("class", "mod"):
                    if name not in classes:
                        classes.append(name)
                elif kind == "fn":
                    if name not in functions:
                        functions.append(name)

        if classes:
            names = ", ".join(classes[:3])
            suffix = " ..." if len(classes) > 3 else ""
            return f"定义类型: {names}{suffix}"
        if functions:
            names = ", ".join(functions[:3])
            suffix = " ..." if len(functions) > 3 else ""
            return f"定义函数: {names}{suffix}"

        return "模块文件"