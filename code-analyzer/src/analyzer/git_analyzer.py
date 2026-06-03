"""
Git 历史分析器：分析提交历史、高频修改文件、贡献者等。
"""
from __future__ import annotations

import subprocess
import os
from pathlib import Path
from typing import Any
from datetime import datetime, timezone


class GitAnalyzer:
    """Git 仓库历史分析器。"""

    def __init__(self, project_root: str):
        self._root = Path(project_root).resolve()
        self._git_dir = self._find_git_dir()

    def _find_git_dir(self) -> str | None:
        """查找 .git 目录。"""
        current = self._root
        while current != current.parent:
            git_path = current / ".git"
            if git_path.exists():
                return str(current)
            current = current.parent
        return None

    @property
    def is_git_repo(self) -> bool:
        return self._git_dir is not None

    def analyze(self) -> dict[str, Any]:
        """执行 Git 历史分析。"""
        if not self._git_dir:
            return {"is_git_repo": False}

        result: dict[str, Any] = {"is_git_repo": True}

        try:
            result.update(self._get_basic_info())
            result.update(self._get_top_changed_files())
            result.update(self._get_contributors())
            result.update(self._get_commit_activity())
            result.update(self._get_recent_commits(10))
        except Exception:
            pass

        return result

    def _run(self, args: list[str]) -> str:
        """运行 git 命令。"""
        try:
            r = subprocess.run(
                ["git"] + args,
                cwd=self._git_dir,
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
            return r.stdout.strip()
        except Exception:
            return ""

    def _get_basic_info(self) -> dict:
        """获取基本信息。"""
        branches = self._run(["branch", "-a"]).split("\n")
        current_branch = ""
        branch_count = 0
        for b in branches:
            b = b.strip()
            if b.startswith("* "):
                current_branch = b[2:]
            if b:
                branch_count += 1

        total_commits = 0
        try:
            total_commits = int(self._run(["rev-list", "--count", "HEAD"]))
        except ValueError:
            pass

        tags = [t.strip() for t in self._run(["tag"]).split("\n") if t.strip()]

        return {
            "current_branch": current_branch,
            "branch_count": branch_count,
            "total_commits": total_commits,
            "tags": tags[:10],
        }

    def _get_top_changed_files(self) -> dict:
        """获取修改最频繁的文件。"""
        output = self._run(["log", "--pretty=format:", "--name-only", "-n", "500"])
        files = [f for f in output.split("\n") if f.strip()]

        from collections import Counter
        counter = Counter(files)
        top = counter.most_common(20)

        return {
            "top_changed_files": [
                {"file": f, "changes": c} for f, c in top
            ],
        }

    def _get_contributors(self) -> dict:
        """获取贡献者统计。"""
        output = self._run(["shortlog", "-sn", "HEAD"])
        contributors = []
        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                try:
                    commits = int(parts[0].strip())
                    name = parts[1].strip()
                    contributors.append({"name": name, "commits": commits})
                except ValueError:
                    pass

        contributors.sort(key=lambda x: x["commits"], reverse=True)

        return {
            "contributors": contributors[:10],
            "contributor_count": len(contributors),
        }

    def _get_commit_activity(self) -> dict:
        """获取提交活动统计。"""
        # 按月份统计
        output = self._run(["log", "--pretty=format:%ad", "--date=short", "-n", "500"])
        dates = output.split("\n")

        monthly: dict[str, int] = {}
        for date_str in dates:
            if len(date_str) >= 7:
                month = date_str[:7]
                monthly[month] = monthly.get(month, 0) + 1

        # 按周几统计
        weekly: dict[str, int] = {}
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        output2 = self._run(["log", "--pretty=format:%ad", "--date=format:%a", "-n", "500"])
        for day in output2.split("\n"):
            day = day.strip()
            if day:
                weekly[day] = weekly.get(day, 0) + 1

        return {
            "monthly_activity": [
                {"month": k, "commits": v}
                for k, v in sorted(monthly.items())[-12:]
            ],
            "weekly_activity": [
                {"day": d, "commits": weekly.get(d, 0)}
                for d in day_names
            ],
        }

    def _get_recent_commits(self, n: int = 10) -> dict:
        """获取最近提交。"""
        output = self._run([
            "log", f"-{n}", "--pretty=format:%h|%an|%ad|%s",
            "--date=short"
        ])
        commits = []
        for line in output.split("\n"):
            parts = line.split("|", 3)
            if len(parts) == 4:
                commits.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "message": parts[3][:80],
                })

        return {"recent_commits": commits}