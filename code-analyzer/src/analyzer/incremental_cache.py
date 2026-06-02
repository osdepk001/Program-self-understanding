from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Optional

from ..graph.dependency_graph import FileNode


class IncrementalCache:
    """管理文件哈希缓存，支持增量分析——只重新分析变更过的文件。"""

    def __init__(self, cache_path: str) -> None:
        self._cache_path = Path(cache_path)
        self._hashes: dict[str, str] = {}
        self._nodes: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self._cache_path.exists():
            return
        try:
            data = json.loads(self._cache_path.read_text(encoding="utf-8"))
            self._hashes = data.get("hashes", {})
            self._nodes = data.get("nodes", {})
        except (json.JSONDecodeError, OSError):
            self._hashes = {}
            self._nodes = {}

    def save(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "hashes": self._hashes,
            "nodes": self._nodes,
        }
        self._cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_cached_node(self, relative_path: str) -> Optional[dict]:
        return self._nodes.get(relative_path)

    def put_node(self, relative_path: str, node_data: dict) -> None:
        self._nodes[relative_path] = node_data

    def file_changed(self, file_path: str) -> bool:
        abs_path = str(Path(file_path).resolve())
        current_hash = self._compute_hash(abs_path)
        if current_hash is None:
            return True
        previous = self._hashes.get(abs_path)
        return previous != current_hash

    def file_removed(self, file_path: str) -> bool:
        abs_path = str(Path(file_path).resolve())
        return not os.path.exists(abs_path)

    def update_hash(self, file_path: str) -> None:
        abs_path = str(Path(file_path).resolve())
        current_hash = self._compute_hash(abs_path)
        if current_hash:
            self._hashes[abs_path] = current_hash

    def remove_stale_entries(self, valid_abs_paths: set[str], valid_rel_paths: set[str]) -> None:
        stale_hashes = [k for k in self._hashes if k not in valid_abs_paths]
        for k in stale_hashes:
            del self._hashes[k]
        stale_nodes = [k for k in self._nodes if k not in valid_rel_paths]
        for k in stale_nodes:
            del self._nodes[k]

    def get_stats(self) -> dict:
        total = len(self._hashes)
        with_nodes = len(self._nodes)
        return {"cached_files": total, "cached_nodes": with_nodes}

    @staticmethod
    def _compute_hash(file_path: str) -> Optional[str]:
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            return hashlib.sha256(content).hexdigest()
        except (OSError, IOError):
            return None