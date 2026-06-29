from __future__ import annotations

import ast

from mycopatch.core.models import EvidenceItem


def analyze_datetime_risks(source: str) -> list[EvidenceItem]:
    """Return deterministic AST-backed datetime risk evidence."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    analyzer = _DateTimeRiskVisitor(source.splitlines())
    analyzer.visit(tree)
    return analyzer.results()


class _DateTimeRiskVisitor(ast.NodeVisitor):
    def __init__(self, lines: list[str]) -> None:
        self.lines = lines
        self._evidence: list[EvidenceItem] = []
        self._seen: set[tuple[int, str]] = set()
        self._risky_names: dict[str, str] = {}

    def results(self) -> list[EvidenceItem]:
        return sorted(self._evidence, key=lambda item: (item.line_number, item.pattern))

    def visit_Assign(self, node: ast.Assign) -> None:
        pattern = self._risky_call_pattern(node.value)
        if pattern:
            for target in node.targets:
                for name in _target_names(target):
                    self._risky_names[name] = pattern
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            pattern = self._risky_call_pattern(node.value)
            if pattern:
                for name in _target_names(node.target):
                    self._risky_names[name] = pattern
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        pattern = self._risky_call_pattern(node)
        if pattern:
            self._add(node, pattern, "datetime_call")
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        operands = [node.left, *node.comparators]
        if any(self._contains_risky_datetime(operand) for operand in operands):
            self._add(node, "timezone-naive comparison", "datetime_comparison")
        self.generic_visit(node)

    def _contains_risky_datetime(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Name) and node.id in self._risky_names:
            return True
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and self._risky_call_pattern(child):
                return True
            if isinstance(child, ast.Name) and child.id in self._risky_names:
                return True
        return False

    def _risky_call_pattern(self, node: ast.AST) -> str | None:
        if not isinstance(node, ast.Call):
            return None

        call_name = _call_name(node.func)
        normalized = _normalize_call_name(call_name)

        if normalized == "datetime.now" and _call_has_no_timezone(node):
            return "datetime.now()"
        if normalized == "datetime.utcnow":
            return "datetime.utcnow()"
        if normalized == "date.today":
            return "date.today()"
        if normalized == "datetime" and _datetime_constructor_is_naive(node):
            return "datetime(...)"
        if isinstance(node.func, ast.Attribute) and node.func.attr == "replace":
            if any(keyword.arg == "tzinfo" for keyword in node.keywords):
                return "replace(tzinfo=...)"
        return None

    def _add(self, node: ast.AST, pattern: str, kind: str) -> None:
        line_number = getattr(node, "lineno", 0)
        key = (line_number, pattern)
        if line_number <= 0 or key in self._seen:
            return
        self._seen.add(key)
        self._evidence.append(
            EvidenceItem(
                line_number=line_number,
                pattern=pattern,
                snippet=_line_at(self.lines, line_number),
                kind=kind,
            )
        )


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _normalize_call_name(name: str) -> str:
    if name in {"datetime.datetime.now", "datetime.now"}:
        return "datetime.now"
    if name in {"datetime.datetime.utcnow", "datetime.utcnow"}:
        return "datetime.utcnow"
    if name in {"datetime.date.today", "date.today"}:
        return "date.today"
    if name in {"datetime.datetime", "datetime"}:
        return "datetime"
    return name


def _call_has_no_timezone(node: ast.Call) -> bool:
    if node.args:
        return False
    for keyword in node.keywords:
        if keyword.arg in {"tz", "tzinfo"} and not _is_none(keyword.value):
            return False
    return True


def _datetime_constructor_is_naive(node: ast.Call) -> bool:
    for keyword in node.keywords:
        if keyword.arg == "tzinfo" and not _is_none(keyword.value):
            return False
    return True


def _is_none(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _target_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        names: list[str] = []
        for item in node.elts:
            names.extend(_target_names(item))
        return names
    return []


def _line_at(lines: list[str], line_number: int) -> str:
    if 1 <= line_number <= len(lines):
        return lines[line_number - 1].strip()[:180]
    return ""
