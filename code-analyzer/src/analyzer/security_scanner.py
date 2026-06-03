"""
安全基础扫描器：检测硬编码密钥、敏感信息、SQL 注入风险等常见安全问题。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from enum import Enum


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class SecurityIssue:
    def __init__(self, rule_id: str, title: str, severity: Severity,
                 file_path: str, line: int, snippet: str = "",
                 description: str = ""):
        self.rule_id = rule_id
        self.title = title
        self.severity = severity
        self.file_path = file_path
        self.line = line
        self.snippet = snippet
        self.description = description

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "severity": self.severity.value,
            "file": self.file_path,
            "line": self.line,
            "snippet": self.snippet[:80],
            "description": self.description,
        }


class SecurityScanner:
    """安全基础扫描器。"""

    # 敏感文件扩展名
    SENSITIVE_EXTS = {".env", ".pem", ".key", ".pfx", ".p12", ".jks", ".keystore",
                      ".credentials", ".secret", ".token", ".htpasswd"}

    # 高危文件名
    SENSITIVE_FILENAMES = {"id_rsa", "id_ed25519", "id_ecdsa", "known_hosts",
                           "authorized_keys", "Dockerfile", "docker-compose.yml"}

    def __init__(self, project_root: str):
        self._root = Path(project_root).resolve()
        self._issues: list[SecurityIssue] = []

    def scan(self, files: list[Path]) -> list[SecurityIssue]:
        self._issues = []

        for file_path in files:
            rel_path = self._relative(file_path)

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            # 跳过 node_modules, vendor, .git 等
            if self._should_skip(rel_path):
                continue

            ext = file_path.suffix.lower()
            filename = file_path.name.lower()

            # 敏感文件检测
            if ext in self.SENSITIVE_EXTS:
                self._issues.append(SecurityIssue(
                    rule_id="SEC-001", title="敏感文件",
                    severity=Severity.HIGH, file_path=rel_path, line=0,
                    snippet=f"检测到敏感文件: {filename}",
                    description="该文件可能包含敏感信息（密钥、凭证等），建议确认是否应提交到版本控制。"
                ))
                continue

            if filename in self.SENSITIVE_FILENAMES:
                self._issues.append(SecurityIssue(
                    rule_id="SEC-001", title="敏感文件",
                    severity=Severity.MEDIUM, file_path=rel_path, line=0,
                    snippet=f"检测到敏感文件: {filename}",
                    description="该文件可能包含敏感信息。"
                ))

            # 扫描内容
            self._scan_hardcoded_secrets(file_path, content, rel_path)
            self._scan_sql_injection(file_path, content, rel_path, ext)
            self._scan_xss(file_path, content, rel_path, ext)
            self._scan_command_injection(file_path, content, rel_path, ext)
            self._scan_unsafe_deserialization(file_path, content, rel_path, ext)
            self._scan_debug_mode(file_path, content, rel_path, ext)
            self._scan_weak_crypto(file_path, content, rel_path, ext)

        return self._issues

    def _should_skip(self, path: str) -> bool:
        skip_dirs = ["node_modules", "vendor", ".git", "__pycache__", "dist",
                     "build", "target", "venv", ".venv", "env", ".env",
                     "bower_components", ".next", ".nuxt", "coverage",
                     ".pytest_cache", ".mypy_cache", ".tox", "eggs"]
        parts = path.replace("\\", "/").split("/")
        return any(p in skip_dirs for p in parts)

    # ==================== 硬编码密钥 ====================

    def _scan_hardcoded_secrets(self, file_path: Path, content: str, rel_path: str) -> None:
        lines = content.split("\n")

        # API Key 模式
        patterns = [
            (r'(?:api[_-]?key|apikey|api[_-]?secret|secret[_-]?key|access[_-]?key|auth[_-]?token)\s*[:=]\s*["\']([A-Za-z0-9_\-]{10,})["\']',
             Severity.HIGH, "硬编码 API 密钥"),
            (r'(?:password|passwd|pwd)\s*[:=]\s*["\'](?!.*(?:changeme|password|test|example|your))[^"\']{4,}["\']',
             Severity.HIGH, "硬编码密码"),
            (r'(?:private[_-]?key|secret)\s*[:=]\s*["\'](?:-----BEGIN|MII|MIJ)[^"\']+["\']',
             Severity.CRITICAL, "硬编码私钥"),
            (r'(?:aws[_-]?access[_-]?key[_-]?id|aws[_-]?secret[_-]?access[_-]?key)\s*[:=]\s*["\'][A-Za-z0-9/+]{16,}["\']',
             Severity.CRITICAL, "AWS 凭证"),
            (r'sk-[A-Za-z0-9]{20,}',
             Severity.CRITICAL, "OpenAI API Key"),
            (r'(?:jdbc|mysql|postgresql|mongodb|redis)://[^:]+:[^@]+@',
             Severity.HIGH, "数据库连接字符串包含密码"),
            (r'(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}',
             Severity.CRITICAL, "GitHub Token"),
            (r'eyJ[A-Za-z0-9\-_]{20,}\.[A-Za-z0-9\-_]{20,}\.[A-Za-z0-9\-_]{10,}',
             Severity.MEDIUM, "JWT Token"),
        ]

        for pattern, severity, title in patterns:
            for m in re.finditer(pattern, content, re.IGNORECASE):
                line_no = content[:m.start()].count("\n") + 1
                snippet = m.group(0)
                # 屏蔽敏感信息
                masked = snippet[:20] + "***" + snippet[-5:] if len(snippet) > 30 else snippet[:10] + "***"

                self._issues.append(SecurityIssue(
                    rule_id="SEC-002", title=title,
                    severity=severity, file_path=rel_path,
                    line=line_no, snippet=masked,
                    description=f"检测到 {title}，建议使用环境变量或密钥管理服务。"
                ))

    # ==================== SQL 注入 ====================

    def _scan_sql_injection(self, file_path: Path, content: str, rel_path: str, ext: str) -> None:
        """检测潜在的 SQL 注入风险。"""
        # Python 字符串拼接 SQL
        if ext in (".py",):
            for m in re.finditer(r'(?:execute|cursor\.execute|\.raw)\s*\(\s*(?:f["\']|["\'][^"\']*%[sd]|["\']\s*\+|["\']\s*\.format)', content):
                line_no = content[:m.start()].count("\n") + 1
                self._issues.append(SecurityIssue(
                    rule_id="SEC-003", title="潜在 SQL 注入",
                    severity=Severity.HIGH, file_path=rel_path,
                    line=line_no, snippet=m.group(0)[:60],
                    description="使用了字符串拼接构造 SQL 查询，存在 SQL 注入风险。建议使用参数化查询。"
                ))

        # Java 字符串拼接 SQL
        if ext in (".java",):
            for m in re.finditer(r'(?:Statement|createStatement|executeQuery|executeUpdate)\s*\(', content):
                # 检查上下文是否有拼接
                line_start = max(0, m.start() - 200)
                context = content[line_start:m.start()]
                if "+" in context and ("SELECT" in context.upper() or "INSERT" in context.upper()):
                    line_no = content[:m.start()].count("\n") + 1
                    self._issues.append(SecurityIssue(
                        rule_id="SEC-003", title="潜在 SQL 注入（Java）",
                        severity=Severity.HIGH, file_path=rel_path,
                        line=line_no, snippet="Statement + 字符串拼接",
                        description="使用 Statement 配合字符串拼接存在 SQL 注入风险。建议使用 PreparedStatement。"
                    ))

        # PHP SQL 拼接
        if ext in (".php",):
            for m in re.finditer(r'(?:mysql_query|mysqli_query|pg_query)\s*\(\s*["\'].*\$', content):
                line_no = content[:m.start()].count("\n") + 1
                self._issues.append(SecurityIssue(
                    rule_id="SEC-003", title="潜在 SQL 注入（PHP）",
                    severity=Severity.HIGH, file_path=rel_path,
                    line=line_no, snippet=m.group(0)[:60],
                    description="PHP 直接拼接变量到 SQL 查询，存在 SQL 注入风险。建议使用 PDO 预处理语句。"
                ))

    # ==================== XSS ====================

    def _scan_xss(self, file_path: Path, content: str, rel_path: str, ext: str) -> None:
        if ext in (".js", ".jsx", ".ts", ".tsx", ".html", ".php"):
            # innerHTML 赋值
            for m in re.finditer(r'\.innerHTML\s*=', content):
                line_no = content[:m.start()].count("\n") + 1
                self._issues.append(SecurityIssue(
                    rule_id="SEC-004", title="潜在 XSS 风险",
                    severity=Severity.MEDIUM, file_path=rel_path,
                    line=line_no, snippet=".innerHTML =",
                    description="使用 innerHTML 可能导致 XSS 攻击。建议使用 textContent 或进行 HTML 转义。"
                ))

            # dangerouslySetInnerHTML (React)
            for m in re.finditer(r'dangerouslySetInnerHTML', content):
                line_no = content[:m.start()].count("\n") + 1
                self._issues.append(SecurityIssue(
                    rule_id="SEC-004", title="React XSS 风险",
                    severity=Severity.MEDIUM, file_path=rel_path,
                    line=line_no, snippet="dangerouslySetInnerHTML",
                    description="dangerouslySetInnerHTML 可能造成 XSS 攻击。请确保内容已经过安全处理。"
                ))

        if ext in (".php",):
            # echo $_GET / $_POST
            for m in re.finditer(r'echo\s+\$(?:_GET|_POST|_REQUEST)\[', content):
                line_no = content[:m.start()].count("\n") + 1
                self._issues.append(SecurityIssue(
                    rule_id="SEC-004", title="PHP XSS 风险",
                    severity=Severity.HIGH, file_path=rel_path,
                    line=line_no, snippet=m.group(0)[:40],
                    description="直接输出用户输入到 HTML，存在 XSS 风险。建议使用 htmlspecialchars()。"
                ))

    # ==================== 命令注入 ====================

    def _scan_command_injection(self, file_path: Path, content: str, rel_path: str, ext: str) -> None:
        if ext in (".py",):
            for m in re.finditer(r'(?:os\.system|os\.popen|subprocess\.call|subprocess\.Popen|subprocess\.run)\s*\(', content):
                # 检查是否使用了 shell=True 或用户输入
                context = content[m.start():m.start() + 200]
                if "shell=True" in context:
                    line_no = content[:m.start()].count("\n") + 1
                    self._issues.append(SecurityIssue(
                        rule_id="SEC-005", title="命令注入风险",
                        severity=Severity.HIGH, file_path=rel_path,
                        line=line_no, snippet=m.group(0)[:50],
                        description="使用 shell=True 执行命令可能存在命令注入风险。建议使用参数列表形式。"
                    ))

        if ext in (".php",):
            for m in re.finditer(r'(?:exec|shell_exec|system|passthru)\s*\(', content):
                line_no = content[:m.start()].count("\n") + 1
                self._issues.append(SecurityIssue(
                    rule_id="SEC-005", title="命令注入风险（PHP）",
                    severity=Severity.HIGH, file_path=rel_path,
                    line=line_no, snippet=m.group(0)[:40],
                    description="使用了可能执行系统命令的函数，存在命令注入风险。"
                ))

    # ==================== 不安全反序列化 ====================

    def _scan_unsafe_deserialization(self, file_path: Path, content: str, rel_path: str, ext: str) -> None:
        if ext in (".py",):
            for m in re.finditer(r'(?:pickle\.loads|pickle\.load|yaml\.load\s*\(|marshal\.loads)', content):
                if "yaml" in m.group(0) and "SafeLoader" in content[m.start():m.start() + 100]:
                    continue
                line_no = content[:m.start()].count("\n") + 1
                self._issues.append(SecurityIssue(
                    rule_id="SEC-006", title="不安全反序列化",
                    severity=Severity.HIGH, file_path=rel_path,
                    line=line_no, snippet=m.group(0)[:50],
                    description="pickle/yaml.load 可能导致任意代码执行。建议使用 json 或 yaml.safe_load。"
                ))

        if ext in (".java",):
            for m in re.finditer(r'ObjectInputStream', content):
                line_no = content[:m.start()].count("\n") + 1
                self._issues.append(SecurityIssue(
                    rule_id="SEC-006", title="Java 反序列化风险",
                    severity=Severity.MEDIUM, file_path=rel_path,
                    line=line_no, snippet="ObjectInputStream",
                    description="Java 反序列化可能被利用进行攻击。建议使用白名单验证或替代方案。"
                ))

        if ext in (".php",):
            for m in re.finditer(r'unserialize\s*\(', content):
                line_no = content[:m.start()].count("\n") + 1
                self._issues.append(SecurityIssue(
                    rule_id="SEC-006", title="PHP 反序列化风险",
                    severity=Severity.HIGH, file_path=rel_path,
                    line=line_no, snippet="unserialize(",
                    description="PHP unserialize 可能被利用进行对象注入攻击。"
                ))

    # ==================== 调试模式 ====================

    def _scan_debug_mode(self, file_path: Path, content: str, rel_path: str, ext: str) -> None:
        if ext in (".py",):
            for m in re.finditer(r'DEBUG\s*=\s*True', content):
                line_no = content[:m.start()].count("\n") + 1
                self._issues.append(SecurityIssue(
                    rule_id="SEC-007", title="调试模式开启",
                    severity=Severity.MEDIUM, file_path=rel_path,
                    line=line_no, snippet="DEBUG = True",
                    description="生产环境应关闭 DEBUG 模式，避免泄露敏感信息。"
                ))

        if ext in (".php",):
            for m in re.finditer(r'(?:error_reporting\s*\(\s*E_ALL|display_errors\s*=\s*On|ini_set\s*\(\s*["\']display_errors)', content):
                line_no = content[:m.start()].count("\n") + 1
                self._issues.append(SecurityIssue(
                    rule_id="SEC-007", title="PHP 错误显示开启",
                    severity=Severity.MEDIUM, file_path=rel_path,
                    line=line_no, snippet=m.group(0)[:40],
                    description="生产环境应关闭错误显示，避免泄露代码结构。"
                ))

    # ==================== 弱加密算法 ====================

    def _scan_weak_crypto(self, file_path: Path, content: str, rel_path: str, ext: str) -> None:
        weak_algorithms = ["MD5", "SHA1", "SHA-1", "DES", "RC4", "3DES", "TripleDES"]
        for algo in weak_algorithms:
            # 仅检测密码学上下文中的使用
            for m in re.finditer(rf'(?:MessageDigest|Hash\.|hashlib\.|crypto\.)\w*\b.*{algo}', content, re.IGNORECASE):
                line_no = content[:m.start()].count("\n") + 1
                self._issues.append(SecurityIssue(
                    rule_id="SEC-008", title=f"弱加密算法: {algo}",
                    severity=Severity.MEDIUM, file_path=rel_path,
                    line=line_no, snippet=m.group(0)[:60],
                    description=f"{algo} 已被认为不安全，建议使用 SHA-256 或更强的算法。"
                ))

    def _relative(self, file_path: Path) -> str:
        try:
            return str(file_path.relative_to(self._root)).replace("\\", "/")
        except ValueError:
            return str(file_path)


def build_security_summary(issues: list[SecurityIssue]) -> dict[str, Any]:
    by_severity: dict[str, int] = {}
    for issue in issues:
        by_severity[issue.severity.value] = by_severity.get(issue.severity.value, 0) + 1

    return {
        "total_issues": len(issues),
        "by_severity": by_severity,
        "critical": by_severity.get("critical", 0),
        "high": by_severity.get("high", 0),
        "medium": by_severity.get("medium", 0),
        "low": by_severity.get("low", 0),
        "issues": [i.to_dict() for i in issues[:50]],
    }