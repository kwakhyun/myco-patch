from __future__ import annotations

import ast
import json
import os
from pathlib import Path

from mycopatch.core.models import FileFinding, RepoScanResult, relative_path
from mycopatch.core.js_ts_datetime_analyzer import analyze_js_ts_datetime_risks
from mycopatch.core.paths import IGNORED_DIRS
from mycopatch.core.python_datetime_analyzer import analyze_datetime_risks


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
PYTHON_SUFFIXES = {".py"}
JS_TS_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
JS_TS_TEST_MARKERS = {".test.", ".spec."}


def scan_repository(repo_root: Path | str) -> RepoScanResult:
    root = Path(repo_root).resolve()
    python_files: list[FileFinding] = []
    js_ts_files: list[FileFinding] = []
    framework_hints: set[str] = set()

    for path in _iter_source_files(root):
        if _is_js_ts_file(path):
            finding = scan_js_ts_file(path, root)
            js_ts_files.append(finding)
        else:
            finding = scan_python_file(path, root)
            python_files.append(finding)

        if path.name in {"manage.py"}:
            framework_hints.add("django")
        if any(part == "migrations" for part in path.parts):
            framework_hints.add("django-or-sqlalchemy-migrations")
        if path.name in {"conftest.py"}:
            framework_hints.add("pytest")
        if "fastapi" in " ".join(finding.evidence).lower():
            framework_hints.add("fastapi")

    framework_hints.update(_package_json_hints(root))

    return RepoScanResult(
        repo_root=root.as_posix(),
        python_files=sorted(python_files, key=lambda finding: finding.path),
        js_ts_files=sorted(js_ts_files, key=lambda finding: finding.path),
        ignored_dirs=sorted(IGNORED_DIRS),
        framework_hints=sorted(framework_hints),
    )


def scan_python_file(path: Path, repo_root: Path) -> FileFinding:
    rel_path = relative_path(path, repo_root)
    try:
        text = _read_small_text(path)
    except UnicodeDecodeError:
        text = ""

    datetime_evidence = analyze_datetime_risks(text)
    evidence = _collect_evidence(text, datetime_evidence)
    lowered = f"{rel_path}\n{text}".lower()
    is_test = _is_test_file(path, repo_root)
    imports_datetime = _imports_datetime(text)
    evidence_patterns = {item.pattern for item in datetime_evidence}

    return FileFinding(
        path=rel_path,
        language="python",
        line_count=text.count("\n") + (1 if text else 0),
        imports_datetime=imports_datetime,
        uses_datetime_now="datetime.now()" in evidence_patterns,
        uses_datetime_utcnow="datetime.utcnow()" in evidence_patterns,
        uses_date_today="date.today()" in evidence_patterns,
        uses_naive_datetime_construction="datetime(...)" in evidence_patterns,
        uses_replace_tzinfo="replace(tzinfo=...)" in evidence_patterns,
        uses_timezone_naive_comparison="timezone-naive comparison" in evidence_patterns,
        contains_timezone_keywords=any(keyword in lowered for keyword in TIME_KEYWORDS),
        is_test_file=is_test,
        evidence=evidence,
        datetime_evidence=datetime_evidence,
    )


def scan_js_ts_file(path: Path, repo_root: Path) -> FileFinding:
    rel_path = relative_path(path, repo_root)
    try:
        text = _read_small_text(path)
    except UnicodeDecodeError:
        text = ""

    datetime_evidence = analyze_js_ts_datetime_risks(text)
    evidence = _collect_evidence(text, datetime_evidence)
    lowered = f"{rel_path}\n{text}".lower()
    evidence_patterns = {item.pattern for item in datetime_evidence}
    evidence_kinds = {item.kind for item in datetime_evidence}

    return FileFinding(
        path=rel_path,
        language=_js_ts_language(path),
        line_count=text.count("\n") + (1 if text else 0),
        uses_js_new_date="new Date()" in evidence_patterns
        or 'new Date("YYYY-MM-DD")' in evidence_patterns,
        uses_js_date_now="Date.now()" in evidence_patterns,
        uses_js_date_parse="Date.parse(...)" in evidence_patterns,
        uses_js_date_string_constructor='new Date("YYYY-MM-DD")' in evidence_patterns,
        uses_js_local_date_accessors="js_date_accessor" in evidence_kinds,
        contains_timezone_keywords=any(keyword in lowered for keyword in TIME_KEYWORDS),
        is_test_file=_is_test_file(path, repo_root),
        evidence=evidence,
        datetime_evidence=datetime_evidence,
    )


def _iter_source_files(root: Path) -> list[Path]:
    results: list[Path] = []
    for current_root_raw, dirnames, filenames in os.walk(root):
        current_root = Path(current_root_raw)
        dirnames[:] = sorted(
            directory for directory in dirnames if directory not in IGNORED_DIRS
        )
        for filename in sorted(filenames):
            path = current_root / filename
            if _is_source_file(path):
                results.append(path)
    return results


def _is_source_file(path: Path) -> bool:
    if path.suffix in PYTHON_SUFFIXES:
        return True
    return _is_js_ts_file(path)


def _is_js_ts_file(path: Path) -> bool:
    if path.name.endswith(".d.ts"):
        return False
    return path.suffix in JS_TS_SUFFIXES


def _js_ts_language(path: Path) -> str:
    return "typescript" if path.suffix in {".ts", ".tsx"} else "javascript"


def _read_small_text(path: Path) -> str:
    if path.stat().st_size > MAX_SCAN_BYTES:
        with path.open("r", encoding="utf-8") as handle:
            return handle.read(MAX_SCAN_BYTES)
    return path.read_text(encoding="utf-8")


def _is_test_file(path: Path, repo_root: Path) -> bool:
    rel_parts = path.resolve().relative_to(repo_root.resolve()).parts
    if path.suffix == ".py":
        return (
            path.name.startswith("test_")
            or path.name.endswith("_test.py")
            or (len(rel_parts) > 1 and rel_parts[0] == "tests")
        )

    name = path.name
    return (
        any(marker in name for marker in JS_TS_TEST_MARKERS)
        or any(part in {"tests", "__tests__"} for part in rel_parts)
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


def _collect_evidence(text: str, datetime_evidence: list) -> list[str]:
    snippets: list[str] = []
    for item in datetime_evidence:
        snippets.append(f"L{item.line_number}: {item.snippet}")

    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        lowered = stripped.lower()
        if any(keyword in lowered for keyword in TIME_KEYWORDS):
            snippets.append(f"L{lineno}: {stripped[:180]}")

    deduped: list[str] = []
    seen: set[str] = set()
    for snippet in snippets:
        if snippet not in seen:
            deduped.append(snippet)
            seen.add(snippet)
        if len(deduped) >= 12:
            break
    return deduped


def _package_json_hints(root: Path) -> set[str]:
    package_json = root / "package.json"
    if not package_json.exists() or package_json.stat().st_size > MAX_SCAN_BYTES:
        return set()
    try:
        package = json.loads(package_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return set()

    deps = {
        **package.get("dependencies", {}),
        **package.get("devDependencies", {}),
        **package.get("peerDependencies", {}),
    }
    hints: set[str] = set()
    for name in deps:
        normalized = name.lower()
        if normalized in {"next", "react", "vue", "svelte", "nuxt", "express", "fastify", "nestjs", "@nestjs/core"}:
            hints.add(normalized)
        if normalized in {"jest", "vitest", "mocha", "ava"}:
            hints.add(normalized)
    if package.get("type") == "module":
        hints.add("node-esm")
    return hints
