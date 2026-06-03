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

    cross_refs: dict[str, list[str]] = field(default_factory=dict)

    call_targets: list[dict] = field(default_factory=list)

    unused_imports: list[str] = field(default_factory=list)

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
            "cross_refs": self.cross_refs,
            "call_targets": self.call_targets,
            "unused_imports": self.unused_imports,
            "lines": self.lines,
            "layer": self.layer,
        }


class DependencyGraph:
    """管理整个项目的文件依赖图。"""

    def __init__(self) -> None:
        self._nodes: dict[str, FileNode] = {}
        self._cycles: list[list[str]] = []
        self.project_info: dict = {}
        self.api_endpoints: dict = {}
        self.db_models: dict = {}
        self.quality: dict = {}
        self.git_info: dict = {}
        self.security: dict = {}

    def add_node(self, node: FileNode) -> None:
        self._nodes[node.relative_path] = node

    def get_node(self, relative_path: str) -> Optional[FileNode]:
        return self._nodes.get(relative_path)

    def get_all_nodes(self) -> list[FileNode]:
        return list(self._nodes.values())

    def get_cycles(self) -> list[list[str]]:
        return self._cycles

    def set_project_info(self, info: dict) -> None:
        self.project_info = info

    def set_api_endpoints(self, data: dict) -> None:
        self.api_endpoints = data

    def set_db_models(self, data: dict) -> None:
        self.db_models = data

    def set_quality(self, data: dict) -> None:
        self.quality = data

    def set_git_info(self, data: dict) -> None:
        self.git_info = data

    def set_security(self, data: dict) -> None:
        self.security = data

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
        """通过拓扑排序检测架构分层。

        从叶子节点（不依赖任何项目内文件的文件）出发，
        沿 imported_by 反向边向上 BFS，逐层递增。
        无法通过 BFS 到达的节点（如循环依赖、孤立节点）使用启发式回退。
        """
        # Step 1: 计算 out-degree —— 每个文件有多少个项目内部导入
        out_degree: dict[str, int] = {}
        for node in self._nodes.values():
            if node.relative_path not in out_degree:
                out_degree[node.relative_path] = 0
            for imp in node.imports:
                if imp in self._nodes:
                    out_degree[node.relative_path] += 1
                if imp not in out_degree:
                    out_degree[imp] = 0

        # Step 2: BFS 从叶子节点（out_degree == 0）沿 imported_by 向上
        queue = [k for k, v in out_degree.items() if v == 0 and k in self._nodes]
        layer_map: dict[str, int] = {}
        visited: set[str] = set()

        for path in queue:
            layer_map[path] = 0

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            current_layer = layer_map.get(current, 0)
            node = self._nodes.get(current)
            if node is None:
                continue
            for imported_by_node in node.imported_by:
                if imported_by_node not in self._nodes:
                    continue
                new_layer = current_layer + 1
                if imported_by_node not in layer_map or layer_map[imported_by_node] < new_layer:
                    layer_map[imported_by_node] = new_layer
                if imported_by_node not in visited:
                    queue.append(imported_by_node)

        # Step 3: 为节点分配层级
        layer_names = {0: "foundation", 1: "common", 2: "domain", 3: "application", 4: "interface"}
        for path, node in self._nodes.items():
            if path in layer_map:
                bfs_layer = layer_map[path]
                # 对于 BFS 分配为 foundation 的孤立节点（无内部导入也无被依赖），使用启发式
                if bfs_layer == 0 and len(node.imported_by) == 0:
                    # isolated leaf nodes get heuristic upgrade
                    heuristic = self._heuristic_layer(node)
                    hl = {"foundation": 0, "common": 1, "domain": 2, "application": 3, "interface": 4}
                    if hl.get(heuristic, 0) > 0:
                        node.layer = heuristic
                    else:
                        node.layer = "foundation"
                else:
                    node.layer = layer_names.get(bfs_layer, f"layer_{bfs_layer}")
            else:
                # 启发式回退：基于目录结构和功能描述
                node.layer = self._heuristic_layer(node)

    @staticmethod
    def _heuristic_layer(node: "FileNode") -> str:
        """基于目录结构和功能描述的启发式分层。"""
        rel = node.relative_path.lower().replace("\\", "/")
        purpose = node.purpose.lower() if node.purpose else ""

        # 接口层关键词
        if any(p in rel for p in ("controller", "handler", "router", "api",
                                   "endpoint", "resource", "view", "page",
                                   "component", "screen", "route")):
            return "interface"

        # 应用层关键词
        if any(p in rel for p in ("service", "usecase", "application", "app",
                                   "facade", "middleware", "interceptor", "filter",
                                   "gateway", "builder", "factory", "manager",
                                   "provider", "resolver", "guard", "pipe")):
            return "application"

        # 领域层关键词
        if any(p in rel for p in ("domain", "model", "entity", "core",
                                   "business", "repository", "dao", "mapper",
                                   "dto", "vo", "schema", "aggregate",
                                   "specification", "policy", "rule", "strategy")):
            return "domain"

        # 公共层关键词
        if any(p in rel for p in ("util", "common", "shared", "helper",
                                   "lib", "library", "utils", "config",
                                   "constant", "const", "enum", "type",
                                   "infrastructure", "infra", "base",
                                   "abstract", "exception", "error",
                                   "logger", "logging", "validator")):
            return "common"

        # 基于功能描述的回退
        if any(kw in purpose for kw in ("控制器", "接口", "入口", "路由", "视图", "页面", "组件")):
            return "interface"
        if any(kw in purpose for kw in ("服务", "应用", "用例", "中间件", "拦截", "过滤", "工厂", "管理")):
            return "application"
        if any(kw in purpose for kw in ("实体", "模型", "领域", "仓库", "数据", "存储", "聚合", "策略")):
            return "domain"
        if any(kw in purpose for kw in ("工具", "配置", "常量", "枚举", "基础", "辅助", "异常", "日志", "验证")):
            return "common"

        # 默认：基础层
        return "foundation"

    def get_stats(self) -> dict:
        total_files = len(self._nodes)
        total_lines = sum(n.lines for n in self._nodes.values())
        total_imports = sum(len(n.imports) for n in self._nodes.values())
        total_xrefs = sum(len(n.cross_refs) for n in self._nodes.values())
        total_calls = sum(len(n.call_targets) for n in self._nodes.values())
        total_unused = sum(len(n.unused_imports) for n in self._nodes.values())
        layers = {}
        for n in self._nodes.values():
            name = n.layer or "unknown"
            layers[name] = layers.get(name, 0) + 1
        return {
            "total_files": total_files,
            "total_lines": total_lines,
            "total_imports": total_imports,
            "total_xrefs": total_xrefs,
            "total_calls": total_calls,
            "total_unused": total_unused,
            "layers": layers,
            "cycles": len(self._cycles),
            "api_endpoints": self.api_endpoints.get("total", 0),
            "db_models": self.db_models.get("total_tables", 0),
            "quality_grade": self.quality.get("grade", "N/A"),
            "security_issues": self.security.get("total_issues", 0),
        }