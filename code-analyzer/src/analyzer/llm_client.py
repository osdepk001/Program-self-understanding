from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

from ..graph.dependency_graph import DependencyGraph, FileNode


class LLMAnalyzer:
    """使用 LLM 对每个文件进行语义级别的功能分析。"""

    SYSTEM_PROMPT = """你是一个代码分析专家。请分析给定的源代码文件，用一段简洁的中文描述：
1. 这个文件的主要功能是什么
2. 它在项目中扮演什么角色（例如：数据模型、工具函数、服务层、API路由、配置等）

要求：
- 只输出一段话，不超过100字
- 不要输出列表格式
- 不要包含任何技术实现细节"""

    def __init__(self, config: dict) -> None:
        self._enabled = config.get("enabled", False)
        self._model = config.get("model", "gpt-4o-mini")
        self._timeout = config.get("timeout", 60)
        self._max_concurrency = config.get("max_concurrency", 5)
        self._max_file_chars = config.get("max_file_chars", 8000)

        api_key = config.get("api_key", "") or os.getenv("OPENAI_API_KEY", "")
        api_base = config.get("api_base", "https://api.openai.com/v1")

        self._client: Optional[OpenAI] = None
        if self._enabled and HAS_OPENAI and api_key:
            self._client = OpenAI(api_key=api_key, base_url=api_base, timeout=self._timeout)
        else:
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled and self._client is not None

    def analyze(self, graph: DependencyGraph) -> None:
        if not self.enabled:
            return

        nodes = graph.get_all_nodes()
        nodes_to_analyze = [n for n in nodes if n.purpose_source != "llm"]

        with ThreadPoolExecutor(max_workers=self._max_concurrency) as executor:
            futures = {executor.submit(self._analyze_one, node): node for node in nodes_to_analyze}
            for future in as_completed(futures):
                node = futures[future]
                try:
                    purpose = future.result()
                    if purpose:
                        node.purpose = purpose
                        node.purpose_source = "llm"
                except Exception:
                    pass

    def _analyze_one(self, node: FileNode) -> Optional[str]:
        if self._client is None:
            return None

        try:
            content = Path(node.path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return None

        if len(content) > self._max_file_chars:
            content = content[:self._max_file_chars] + "\n... (内容已截断)"

        user_prompt = f"""文件名: {node.relative_path}
语言: {node.language}
代码行数: {node.lines}

源代码:
```{node.language}
{content}
```"""

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=200,
            )
            result = response.choices[0].message.content
            if result:
                return result.strip()
        except Exception:
            pass

        return None