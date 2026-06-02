from __future__ import annotations

import json
from pathlib import Path

from ..graph.dependency_graph import DependencyGraph


class JSONReporter:
    """将分析结果输出为 JSON 格式。"""

    def generate(self, graph: DependencyGraph, output_dir: str) -> str:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        stats = graph.get_stats()
        files = [node.to_dict() for node in graph.get_all_nodes()]

        files.sort(key=lambda f: f["relative_path"])

        result = {
            "stats": stats,
            "files": files,
        }

        output_file = out_path / "analysis.json"
        output_file.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return str(output_file)