from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FileNode:
    """表示一个源文件的节点，包含依赖关系和功能描述等全部元数据。"""

    path: str
    relative_path: str
    language: str = ""

    purpose: str = ""
    purpose_source: str = ""

    imports: list[str] = field(default_factory=list)
    imported_by: list[str] = field(default_factory=list)

    exports: list[str] = field(default_factory=list)

    lines: int = 0

    layer: str = ""

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "relative_path": self.relative_path,
            "language": self.language,
            "purpose": self.purpose,
            "purpose_source": self.purpose_source,
            "imports": self.imports,
            "imported_by": self.imported_by,
            "exports": self.exports,
            "lines": self.lines,
            "layer": self.layer,
        }


class DependencyGraph:
    """管理整个项目的文件依赖图。"""

    def __init__(self) -> None:
        self._nodes: dict[str, FileNode] = {}
        self._cycles: list[list[str]] = []

    def add_node(self, node: FileNode) -> None:
        self._nodes[node.relative_path] = node

    def get_node(self, relative_path: str) -> Optional[FileNode]:
        return self._nodes.get(relative_path)

    def get_all_nodes(self) -> list[FileNode]:
        return list(self._nodes.values())

    def get_cycles(self) -> list[list[str]]:
        return self._cycles

    def build_reverse_dependencies(self) -> None:
        for node in self._nodes.values():
            for imported_rel_path in node.imports:
                target = self._nodes.get(imported_rel_path)
                if target is not None:
                    if node.relative_path not in target.imported_by:
                        target.imported_by.append(node.relative_path)

    def detect_cycles(self) -> None:
        visited: set[str] = set()
        rec_stack: set[str] = set()
        path: list[str] = []

        def dfs(node_path: str) -> bool:
            visited.add(node_path)
            rec_stack.add(node_path)
            path.append(node_path)

            node = self._nodes.get(node_path)
            if node:
                for imp in node.imports:
                    if imp not in visited:
                        if dfs(imp):
                            return True
                    elif imp in rec_stack:
                        cycle_start = path.index(imp)
                        cycle = path[cycle_start:] + [imp]
                        normalized = self._normalize_cycle(cycle)
                        if normalized not in self._cycles and len(normalized) > 1:
                            self._cycles.append(normalized)
                        return True
                    elif imp == node_path:
                        self._cycles.append([node_path])

            path.pop()
            rec_stack.discard(node_path)
            return False

        for node_key in self._nodes:
            if node_key not in visited:
                dfs(node_key)

    @staticmethod
    def _normalize_cycle(cycle: list[str]) -> list[str]:
        if len(cycle) <= 1:
            return cycle
        doubled = cycle + cycle
        min_idx = 0
        for i in range(1, len(cycle)):
            if doubled[i:i + len(cycle)] < doubled[min_idx:min_idx + len(cycle)]:
                min_idx = i
        return doubled[min_idx:min_idx + len(cycle) - 1]

    def detect_layers(self) -> None:
        in_degree: dict[str, int] = {}
        for node in self._nodes.values():
            if node.relative_path not in in_degree:
                in_degree[node.relative_path] = 0
            for imp in node.imports:
                if imp not in in_degree:
                    in_degree[imp] = 0
                in_degree[node.relative_path] += 1

        queue = [k for k, v in in_degree.items() if v == 0]
        layer_map: dict[str, int] = {}

        for path in queue:
            layer_map[path] = 0

        while queue:
            current = queue.pop(0)
            current_layer = layer_map.get(current, 0)
            node = self._nodes.get(current)
            if node is None:
                continue
            for imported_by in node.imported_by:
                new_layer = current_layer + 1
                if imported_by not in layer_map or layer_map[imported_by] < new_layer:
                    layer_map[imported_by] = new_layer
                queue.append(imported_by)

        layer_names = {0: "foundation", 1: "common", 2: "domain", 3: "application", 4: "interface"}
        for path, layer_num in layer_map.items():
            node = self._nodes.get(path)
            if node:
                node.layer = layer_names.get(layer_num, f"layer_{layer_num}")

    def get_stats(self) -> dict:
        total_files = len(self._nodes)
        total_lines = sum(n.lines for n in self._nodes.values())
        total_imports = sum(len(n.imports) for n in self._nodes.values())
        layers = {}
        for n in self._nodes.values():
            name = n.layer or "unknown"
            layers[name] = layers.get(name, 0) + 1
        return {
            "total_files": total_files,
            "total_lines": total_lines,
            "total_imports": total_imports,
            "layers": layers,
            "cycles": len(self._cycles),
        }