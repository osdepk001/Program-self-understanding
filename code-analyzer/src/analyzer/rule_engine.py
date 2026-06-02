from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..graph.dependency_graph import DependencyGraph


@dataclass
class RuleViolation:
    rule_name: str
    severity: str
    message: str
    file_path: str = ""
    related_file: str = ""


@dataclass
class RuleResult:
    violations: list[RuleViolation] = field(default_factory=list)
    checked_rules: int = 0
    passed_rules: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "warning")

    @property
    def info_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "info")


class RuleEngine:
    """架构约束规则引擎，支持在配置中定义规则并校验依赖图。"""

    def __init__(self, rules_config: dict) -> None:
        self._rules = rules_config.get("rules", [])
        self._config = rules_config

    def validate(self, graph: DependencyGraph) -> RuleResult:
        result = RuleResult()

        if not self._rules:
            return result

        for rule in self._rules:
            result.checked_rules += 1
            rule_type = rule.get("type", "")
            violations = self._validate_rule(rule, graph)
            if violations:
                result.violations.extend(violations)
            else:
                result.passed_rules += 1

        return result

    def _validate_rule(self, rule: dict, graph: DependencyGraph) -> list[RuleViolation]:
        rule_type = rule.get("type", "")
        handlers = {
            "no_dependency": self._validate_no_dependency,
            "layer_rule": self._validate_layer_rule,
            "naming_pattern": self._validate_naming_pattern,
            "disallowed_import": self._validate_disallowed_import,
            "max_dependencies": self._validate_max_dependencies,
            "max_cycle_size": self._validate_max_cycle_size,
        }
        handler = handlers.get(rule_type)
        if handler:
            return handler(rule, graph)
        return []

    def _violation(self, rule: dict, message: str, file_path: str = "", related_file: str = "") -> RuleViolation:
        return RuleViolation(
            rule_name=rule.get("name", rule.get("type", "unknown")),
            severity=rule.get("severity", "warning"),
            message=message,
            file_path=file_path,
            related_file=related_file,
        )

    def _validate_no_dependency(self, rule: dict, graph: DependencyGraph) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        from_pattern = rule.get("from", "")
        to_pattern = rule.get("to", "")

        if not from_pattern or not to_pattern:
            return violations

        from_re = re.compile(from_pattern)
        to_re = re.compile(to_pattern)

        for node in graph.get_all_nodes():
            if not from_re.search(node.relative_path):
                continue
            for imp in node.imports:
                if to_re.search(imp):
                    violations.append(self._violation(
                        rule,
                        f"'{node.relative_path}' 不应依赖 '{imp}'",
                        file_path=node.relative_path,
                        related_file=imp,
                    ))

        return violations

    def _validate_layer_rule(self, rule: dict, graph: DependencyGraph) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        layers = rule.get("layers", {})
        allow = rule.get("allow", [])

        if not layers:
            return violations

        layer_map: dict[str, str] = {}
        for layer_name, pattern in layers.items():
            compiled = re.compile(pattern)
            for node in graph.get_all_nodes():
                if compiled.search(node.relative_path):
                    if node.relative_path not in layer_map:
                        layer_map[node.relative_path] = layer_name

        for node in graph.get_all_nodes():
            node_layer = layer_map.get(node.relative_path, "unknown")
            for imp in node.imports:
                target_layer = layer_map.get(imp, "unknown")
                if node_layer != target_layer:
                    pair = f"{node_layer}->{target_layer}"
                    if pair not in allow:
                        violations.append(self._violation(
                            rule,
                            f"层级违规: '{node.relative_path}' ({node_layer}) 依赖了 '{imp}' ({target_layer})",
                            file_path=node.relative_path,
                            related_file=imp,
                        ))

        return violations

    def _validate_naming_pattern(self, rule: dict, graph: DependencyGraph) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        target_pattern = rule.get("target", ".*")
        naming_regex = rule.get("pattern", "")

        if not naming_regex:
            return violations

        target_re = re.compile(target_pattern)
        name_re = re.compile(naming_regex)

        for node in graph.get_all_nodes():
            if target_re.search(node.relative_path):
                import os
                basename = os.path.basename(node.relative_path)
                name_without_ext = os.path.splitext(basename)[0]
                if not name_re.match(name_without_ext):
                    violations.append(self._violation(
                        rule,
                        f"命名不符合规范: '{node.relative_path}' 与模式 '{naming_regex}' 不匹配",
                        file_path=node.relative_path,
                    ))

        return violations

    def _validate_disallowed_import(self, rule: dict, graph: DependencyGraph) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        disallowed = rule.get("disallowed", [])

        if not disallowed:
            return violations

        for node in graph.get_all_nodes():
            for imp in node.imports:
                for pattern in disallowed:
                    if re.search(pattern, imp):
                        violations.append(self._violation(
                            rule,
                            f"'{node.relative_path}' 导入了禁止的模块 '{imp}' (匹配: {pattern})",
                            file_path=node.relative_path,
                            related_file=imp,
                        ))

        return violations

    def _validate_max_dependencies(self, rule: dict, graph: DependencyGraph) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        max_count = rule.get("max", 20)
        target_pattern = rule.get("target", ".*")

        target_re = re.compile(target_pattern)

        for node in graph.get_all_nodes():
            if target_re.search(node.relative_path):
                dep_count = len(node.imports)
                if dep_count > max_count:
                    violations.append(self._violation(
                        rule,
                        f"'{node.relative_path}' 有 {dep_count} 个依赖，超过上限 {max_count}",
                        file_path=node.relative_path,
                    ))

        return violations

    def _validate_max_cycle_size(self, rule: dict, graph: DependencyGraph) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        max_size = rule.get("max", 2)

        cycles = graph.get_cycles()
        for cycle in cycles:
            if len(cycle) > max_size:
                violations.append(self._violation(
                    rule,
                    f"检测到大小为 {len(cycle)} 的循环依赖: {' -> '.join(cycle)}",
                ))

        return violations