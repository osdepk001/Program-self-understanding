from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path
from typing import Optional

from ..graph.dependency_graph import FileNode


class PythonParser:
    """使用 Python 内置 ast 模块解析源文件，提取导入、导出、功能描述和跨文件符号引用。"""

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

        try:
            tree = ast.parse(source_code, filename=str(abs_path))
        except SyntaxError:
            return None

        source_dir = abs_path.parent
        imports = self._extract_imports(tree, source_dir)
        exports = self._extract_exports(tree)
        purpose = self._extract_purpose(tree)
        cross_refs = self._extract_cross_refs(tree, source_dir)

        return FileNode(
            path=str(abs_path),
            relative_path=str(abs_path.relative_to(self._project_root)).replace(os.sep, "/"),
            language="python",
            purpose=purpose,
            purpose_source="static",
            imports=imports,
            exports=exports,
            cross_refs=cross_refs,
            lines=len(source_code.splitlines()),
        )

    def _extract_imports(self, tree: ast.AST, source_dir: Path) -> list[str]:
        imports: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    resolved = self._resolve_import(alias.name, source_dir)
                    if resolved:
                        imports.append(resolved)

            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                if node.level is not None and node.level > 0:
                    resolved = self._resolve_relative_import(node.module, node.level, source_dir)
                else:
                    resolved = self._resolve_import(node.module, source_dir)
                if resolved:
                    imports.append(resolved)

        return sorted(set(imports))

    def _extract_cross_refs(self, tree: ast.AST, source_dir: Path) -> dict[str, list[str]]:
        """提取跨文件符号引用：追踪每个 import 的符号在代码中是否被实际使用。

        返回 {relative_path: [symbol1, symbol2, ...]} 的映射。
        """
        cross_refs: dict[str, list[str]] = {}

        # Step 1: 建立符号到模块的映射
        #   symbol_name -> resolved_relative_path
        symbol_to_module: dict[str, str] = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    resolved = self._resolve_import(alias.name, source_dir)
                    if resolved:
                        # import X  -> 使用 X 作为名称
                        name = alias.asname if alias.asname else alias.name.split(".")[0]
                        symbol_to_module[name] = resolved

            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                if node.level is not None and node.level > 0:
                    resolved = self._resolve_relative_import(node.module, node.level, source_dir)
                else:
                    resolved = self._resolve_import(node.module, source_dir)
                if resolved:
                    for alias in node.names:
                        if alias.name == "*":
                            # from X import *  — 无法精确追踪，标记为全部使用
                            cross_refs[resolved] = cross_refs.get(resolved, []) + ["*"]
                            continue
                        name = alias.asname if alias.asname else alias.name
                        symbol_to_module[name] = resolved

        if not symbol_to_module:
            return cross_refs

        # Step 2: 遍历代码中所有 Name 节点，收集实际使用的符号
        used_symbols: set[str] = set()
        for node in ast.walk(tree):
            # 跳过导入语句本身中的 Name
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.Name):
                used_symbols.add(node.id)

        # 也收集 Attribute 访问（如 module.func）
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    used_symbols.add(node.value.id)

        # Step 3: 将使用的符号映射回模块
        for symbol, resolved_path in symbol_to_module.items():
            if symbol in used_symbols:
                if resolved_path not in cross_refs:
                    cross_refs[resolved_path] = []
                if symbol not in cross_refs[resolved_path]:
                    cross_refs[resolved_path].append(symbol)

        return cross_refs

    def _resolve_import(self, module_name: str, source_dir: Path) -> Optional[str]:
        parts = module_name.split(".")
        module_path = "/".join(parts)

        search_dirs = [source_dir, self._project_root]
        for search_dir in search_dirs:
            candidates = [
                search_dir / f"{module_path}.py",
                search_dir / module_path / "__init__.py",
            ]
            for candidate in candidates:
                resolved = self._to_relative(candidate)
                if resolved:
                    return resolved

        # Walk up from source_dir to project_root to find the module
        current = source_dir
        while current >= self._project_root:
            candidates = [
                current / f"{module_path}.py",
                current / module_path / "__init__.py",
            ]
            for candidate in candidates:
                resolved = self._to_relative(candidate)
                if resolved:
                    return resolved
            if current == self._project_root:
                break
            current = current.parent

        return None

    def _resolve_relative_import(self, module: str, level: int, source_dir: Path) -> Optional[str]:
        current = source_dir
        for _ in range(level - 1):
            current = current.parent

        parts = module.split(".") if module else []
        module_path = "/".join(parts) if parts else ""
        candidate = current / f"{module_path}.py" if module_path else None
        if candidate:
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved

        candidate = current / module_path / "__init__.py" if module_path else None
        return self._to_relative(candidate)

    def _to_relative(self, candidate: Path) -> Optional[str]:
        try:
            resolved = candidate.resolve()
            if resolved.is_file():
                return str(resolved.relative_to(self._project_root)).replace(os.sep, "/")
        except (ValueError, OSError):
            pass
        return None

    def _extract_exports(self, tree: ast.AST) -> list[str]:
        exports: list[str] = []

        if isinstance(tree, ast.Module) and tree.body:
            first = tree.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, (ast.Constant, ast.Str)):
                pass

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                if not node.name.startswith("_"):
                    exports.append(f"fn:{node.name}")
            elif isinstance(node, ast.ClassDef):
                if not node.name.startswith("_"):
                    exports.append(f"class:{node.name}")
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and not target.id.startswith("_"):
                        if isinstance(target.ctx, ast.Store):
                            exports.append(f"var:{target.id}")

        return exports

    def _extract_purpose(self, tree: ast.AST) -> str:
        if not isinstance(tree, ast.Module) or not tree.body:
            return ""

        first = tree.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, (ast.Constant, ast.Str)):
            docstring = first.value.value if isinstance(first.value, ast.Constant) else first.value.s
            if isinstance(docstring, str):
                line = docstring.strip().split("\n")[0].strip()
                return line

        classes = [node for node in ast.iter_child_nodes(tree) if isinstance(node, ast.ClassDef) and not node.name.startswith("_")]
        functions = [node for node in ast.iter_child_nodes(tree) if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")]

        if classes:
            names = ", ".join(c.name for c in classes[:3])
            suffix = " ..." if len(classes) > 3 else ""
            return f"定义类: {names}{suffix}"
        if functions:
            names = ", ".join(f.name for f in functions[:3])
            suffix = " ..." if len(functions) > 3 else ""
            return f"定义函数: {names}{suffix}"

        return "模块文件"