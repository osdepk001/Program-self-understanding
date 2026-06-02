from __future__ import annotations

from pathlib import Path

from ..graph.dependency_graph import DependencyGraph


class MarkdownReporter:
    """将分析结果输出为 Markdown 格式，可选包含 Mermaid 依赖图。"""

    def __init__(self, include_mermaid: bool = True) -> None:
        self._include_mermaid = include_mermaid

    def generate(self, graph: DependencyGraph, output_dir: str) -> str:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        lines: list[str] = []
        self._write_header(lines, graph)
        self._write_stats(lines, graph)
        if self._include_mermaid:
            self._write_mermaid(lines, graph)
        self._write_file_details(lines, graph)

        output_file = out_path / "analysis.md"
        output_file.write_text("\n".join(lines), encoding="utf-8")
        return str(output_file)

    def _write_header(self, lines: list[str], graph: DependencyGraph) -> None:
        lines.append("# 项目代码分析报告")
        lines.append("")
        lines.append(f"> 自动生成于分析工具")
        lines.append("")
        lines.append("---")
        lines.append("")

    def _write_stats(self, lines: list[str], graph: DependencyGraph) -> None:
        stats = graph.get_stats()
        lines.append("## 项目概览")
        lines.append("")
        lines.append(f"| 指标 | 数值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 总文件数 | {stats['total_files']} |")
        lines.append(f"| 总代码行 | {stats['total_lines']} |")
        lines.append(f"| 总依赖关系 | {stats['total_imports']} |")
        lines.append("")

        if stats.get("layers"):
            lines.append("### 架构分层")
            lines.append("")
            lines.append("| 层级 | 文件数 |")
            lines.append("|------|--------|")
            for layer_name, count in sorted(stats["layers"].items()):
                lines.append(f"| {layer_name} | {count} |")
            lines.append("")

    def _write_mermaid(self, lines: list[str], graph: DependencyGraph) -> None:
        nodes = graph.get_all_nodes()
        if not nodes:
            return

        lines.append("## 依赖关系图")
        lines.append("")
        lines.append("```mermaid")
        lines.append("graph TD")
        node_ids: dict[str, str] = {}
        for i, node in enumerate(nodes):
            node_id = f"N{i}"
            node_ids[node.relative_path] = node_id
            label = node.relative_path.replace("/", "/<br/>")
            lines.append(f"    {node_id}[\"{label}\"]")

        lines.append("")
        for node in nodes:
            source_id = node_ids[node.relative_path]
            for imp in node.imports:
                target_id = node_ids.get(imp)
                if target_id:
                    lines.append(f"    {source_id} --> {target_id}")

        lines.append("```")
        lines.append("")

    def _write_file_details(self, lines: list[str], graph: DependencyGraph) -> None:
        nodes = sorted(graph.get_all_nodes(), key=lambda n: n.relative_path)
        if not nodes:
            lines.append("## 文件详情")
            lines.append("")
            lines.append("未找到可分析的文件。")
            return

        lines.append("## 文件详情")
        lines.append("")

        for node in nodes:
            lines.append(f"### `{node.relative_path}`")
            lines.append("")

            label_map = {
                "foundation": "基础层",
                "common": "公共层",
                "domain": "领域层",
                "application": "应用层",
                "interface": "接口层",
            }

            lines.append(f"- **语言**: {node.language}")
            lines.append(f"- **代码行数**: {node.lines}")
            if node.layer:
                layer_label = label_map.get(node.layer, node.layer)
                lines.append(f"- **架构层级**: {layer_label}")
            lines.append(f"- **功能描述**: {node.purpose or '(暂无)'}")
            lines.append(f"- **分析来源**: {node.purpose_source or 'static'}")
            lines.append("")

            if node.exports:
                exports_str = ", ".join(f"`{e}`" for e in node.exports[:10])
                if len(node.exports) > 10:
                    exports_str += f" ...（共 {len(node.exports)} 个）"
                lines.append(f"- **对外导出**: {exports_str}")
                lines.append("")

            if node.imports:
                deps = ", ".join(f"[`{d}`](#{d.replace('/', '').replace('.', '').replace('_', '').lower()})" for d in node.imports[:8])
                if len(node.imports) > 8:
                    deps += f" ...（共 {len(node.imports)} 个）"
                lines.append(f"- **依赖文件**: {deps}")
                lines.append("")

            if node.imported_by:
                users = ", ".join(f"`{u}`" for u in node.imported_by[:8])
                if len(node.imported_by) > 8:
                    users += f" ...（共 {len(node.imported_by)} 个）"
                lines.append(f"- **被引用者**: {users}")
                lines.append("")

            lines.append("---")
            lines.append("")