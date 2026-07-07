from __future__ import annotations

import ast

from mycopatch.core.models import EvidenceItem


def analyze_python_bug_patterns(source: str) -> list[EvidenceItem]:
    """Return deterministic AST-backed evidence for common Python bug patterns."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    analyzer = _PythonBugPatternVisitor(source.splitlines())
    analyzer.visit(tree)
    return analyzer.results()


class _PythonBugPatternVisitor(ast.NodeVisitor):
    def __init__(self, lines: list[str]) -> None:
        self.lines = lines
        self._evidence: list[EvidenceItem] = []
        self._seen: set[tuple[int, str]] = set()

    def results(self) -> list[EvidenceItem]:
        return sorted(self._evidence, key=lambda item: (item.line_number, item.pattern))

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function_defaults(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function_defaults(node)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if _is_broad_exception(node.type) and _swallows_exception(node.body):
            self._add(node, "broad exception swallowing", "broad_exception")
        self.generic_visit(node)

    def _check_function_defaults(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        defaults = [*node.args.defaults, *(item for item in node.args.kw_defaults if item is not None)]
        if any(_is_mutable_default(default) for default in defaults):
            self._add(node, "mutable default argument", "mutable_default")

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


def _is_mutable_default(node: ast.AST) -> bool:
    if isinstance(node, (ast.List, ast.Dict, ast.Set)):
        return True
    if isinstance(node, ast.Call):
        return _call_name(node.func) in {"list", "dict", "set"}
    return False


def _is_broad_exception(node: ast.AST | None) -> bool:
    if node is None:
        return True
    names = [_call_name(item) for item in node.elts] if isinstance(node, ast.Tuple) else [_call_name(node)]
    return any(name in {"Exception", "BaseException"} for name in names)


def _swallows_exception(body: list[ast.stmt]) -> bool:
    meaningful = [statement for statement in body if not isinstance(statement, ast.Expr) or not _is_docstring(statement)]
    if not meaningful:
        return True
    return all(_is_swallow_statement(statement) for statement in meaningful)


def _is_swallow_statement(statement: ast.stmt) -> bool:
    if isinstance(statement, (ast.Pass, ast.Continue, ast.Break)):
        return True
    if isinstance(statement, ast.Return):
        return statement.value is None or _is_none(statement.value)
    if isinstance(statement, ast.Expr):
        return isinstance(statement.value, ast.Constant) and statement.value.value is Ellipsis
    return False


def _is_docstring(statement: ast.Expr) -> bool:
    return isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str)


def _is_none(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _line_at(lines: list[str], line_number: int) -> str:
    if 1 <= line_number <= len(lines):
        return lines[line_number - 1].strip()[:180]
    return ""
