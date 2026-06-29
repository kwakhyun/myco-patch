from __future__ import annotations

import ast
import os
from pathlib import Path

from mycopatch.core.models import FileFinding, RepoScanResult, relative_path
from mycopatch.core.paths import IGNORED_DIRS


TIME_KEYWORDS = {
    "billing",
    "invoice",
    "subscription",
    "schedule",
    "expiry",
    "expiration",
    "deadline",
    "renewal",
    "payment",
    "report",
}
MAX_SCAN_BYTES = 512_000


def scan_repository(repo_root: Path | str) -> RepoScanResult:
    root = Path(repo_root).resolve()
    files: list[FileFinding] = []
    framework_hints: set[str] = set()

    for path in _iter_python_files(root):
        finding = scan_python_file(path, root)
        files.append(finding)
        if path.name in {"manage.py"}:
            framework_hints.add("django")
        if any(part == "migrations" for part in path.parts):
            framework_hints.add("django-or-sqlalchemy-migrations")
        if path.name in {"conftest.py"}:
            framework_hints.add("pytest")
        if "fastapi" in " ".join(finding.evidence).lower():
            framework_hints.add("fastapi")

    return RepoScanResult(
        repo_root=root.as_posix(),
        python_files=sorted(files, key=lambda finding: finding.path),
        ignored_dirs=sorted(IGNORED_DIRS),
        framework_hints=sorted(framework_hints),
    )


def scan_python_file(path: Path, repo_root: Path) -> FileFinding:
    rel_path = relative_path(path, repo_root)
    try:
        text = _read_small_text(path)
    except UnicodeDecodeError:
        text = ""

    evidence = _collect_evidence(text)
    lowered = f"{rel_path}\n{text}".lower()
    is_test = _is_test_file(path, repo_root)
    imports_datetime = _imports_datetime(text)

    return FileFinding(
        path=rel_path,
        line_count=text.count("\n") + (1 if text else 0),
        imports_datetime=imports_datetime,
        uses_datetime_now="datetime.now" in text,
        uses_datetime_utcnow="datetime.utcnow" in text,
        uses_date_today="date.today" in text,
        uses_naive_datetime_construction=_uses_naive_datetime_construction(text),
        contains_timezone_keywords=any(keyword in lowered for keyword in TIME_KEYWORDS),
        is_test_file=is_test,
        evidence=evidence,
    )


def _iter_python_files(root: Path) -> list[Path]:
    results: list[Path] = []
    for current_root_raw, dirnames, filenames in os.walk(root):
        current_root = Path(current_root_raw)
        dirnames[:] = sorted(
            directory for directory in dirnames if directory not in IGNORED_DIRS
        )
        for filename in sorted(filenames):
            if filename.endswith(".py"):
                results.append(current_root / filename)
    return results


def _read_small_text(path: Path) -> str:
    if path.stat().st_size > MAX_SCAN_BYTES:
        with path.open("r", encoding="utf-8") as handle:
            return handle.read(MAX_SCAN_BYTES)
    return path.read_text(encoding="utf-8")


def _is_test_file(path: Path, repo_root: Path) -> bool:
    rel_parts = path.resolve().relative_to(repo_root.resolve()).parts
    return (
        path.name.startswith("test_")
        or path.name.endswith("_test.py")
        or (len(rel_parts) > 1 and rel_parts[0] == "tests")
    )


def _imports_datetime(text: str) -> bool:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return "import datetime" in text or "from datetime import" in text

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "datetime" or alias.name.startswith("datetime."):
                    return True
        if isinstance(node, ast.ImportFrom) and node.module == "datetime":
            return True
    return False


def _uses_naive_datetime_construction(text: str) -> bool:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return "datetime(" in text

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name not in {"datetime", "datetime.datetime"}:
            continue
        if not any(keyword.arg == "tzinfo" for keyword in node.keywords):
            return True
    return False


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _collect_evidence(text: str) -> list[str]:
    snippets: list[str] = []
    patterns = ["datetime.now", "datetime.utcnow", "date.today", "datetime("]
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        lowered = stripped.lower()
        if any(pattern in stripped for pattern in patterns) or any(
            keyword in lowered for keyword in TIME_KEYWORDS
        ):
            snippets.append(f"L{lineno}: {stripped[:180]}")
        if len(snippets) >= 8:
            break
    return snippets
