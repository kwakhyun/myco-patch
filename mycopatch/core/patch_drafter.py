from __future__ import annotations

import ast
import difflib
import hashlib
import io
import re
import tokenize
from pathlib import Path

from mycopatch.core.memory import append_memory_event, read_memory_events
from mycopatch.core.models import GuardedPatchDraft, utc_now
from mycopatch.core.paths import get_paths


MAX_PATCH_SOURCE_BYTES = 512_000


def create_guarded_patch_drafts(
    repo_root: Path | str,
) -> tuple[list[GuardedPatchDraft], list[str]]:
    paths = get_paths(repo_root)
    paths.patch_drafts.mkdir(parents=True, exist_ok=True)
    failures = [event for event in read_memory_events(repo_root) if event.event_type == "probe_failed"]
    drafts: list[GuardedPatchDraft] = []
    rejected: list[str] = []
    seen: set[tuple[str, str]] = set()

    for event in failures:
        probe = event.payload.get("probe") if isinstance(event.payload.get("probe"), dict) else {}
        target_file = str(probe.get("target_file") or "")
        risk_type = str(probe.get("risk_type") or "")
        key = (target_file, risk_type)
        if key in seen:
            continue
        seen.add(key)

        failure_kind = str(event.payload.get("failure_kind") or "static_marker")
        draft, reason = _draft_failure(
            paths.repo_root,
            paths.patch_drafts,
            probe,
            failure_kind=failure_kind,
        )
        if draft is None:
            rejected.append(f"{target_file or 'unknown'}: {reason}")
            continue
        drafts.append(draft)
        append_memory_event(repo_root, "patch_draft_created", {"draft": draft.json_dict()})

    if rejected:
        append_memory_event(
            repo_root,
            "patch_draft_ineligible",
            {"count": len(rejected), "reasons": rejected},
        )
    _write_guarded_patch_report(paths.guarded_patch_report, drafts, rejected)
    return drafts, rejected


def _draft_failure(
    root: Path,
    output_dir: Path,
    probe: dict,
    *,
    failure_kind: str,
) -> tuple[GuardedPatchDraft | None, str]:
    if probe.get("mode") != "aggressive":
        return None, "only an explicitly generated aggressive probe failure is eligible"
    if probe.get("risk_type") != "timezone_boundary":
        return None, "no deterministic guarded transformation exists for this risk type"

    target_file = str(probe.get("target_file") or "")
    target, path_error = _safe_target(root, target_file)
    if target is None:
        return None, path_error
    if target.suffix != ".py":
        return None, "the v0.7 draft transformation currently supports Python only"
    if target.stat().st_size > MAX_PATCH_SOURCE_BYTES:
        return None, "target file exceeds the guarded patch size limit"

    try:
        source = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None, "target file is not valid UTF-8"

    patched, transform_error = _replace_datetime_utcnow(source)
    if patched is None:
        return None, transform_error

    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    slug = _slugify(target_file)
    patch_name = f"patch_datetime_utcnow_{slug}.patch"
    patch_path = output_dir / patch_name
    rollback_path = output_dir / f"patch_datetime_utcnow_{slug}.rollback.md"
    patch_text = _unified_diff(target_file, source, patched)
    patch_path.write_text(patch_text, encoding="utf-8")
    rollback_path.write_text(
        _rollback_text(target_file, patch_path.name, source_hash),
        encoding="utf-8",
    )
    evidence = [str(item) for item in probe.get("evidence", [])][:8]
    return (
        GuardedPatchDraft(
            id=f"datetime_utcnow_{slug}",
            target_file=target_file,
            risk_type="timezone_boundary",
            source_sha256=source_hash,
            patch_path=patch_path.relative_to(root).as_posix(),
            rollback_path=rollback_path.relative_to(root).as_posix(),
            transformation="datetime.utcnow() -> datetime.now(timezone.utc)",
            evidence=evidence,
            evidence_level=(
                "behavioral_regression"
                if failure_kind == "behavioral_regression"
                else "static_marker"
            ),
        ),
        "",
    )


def _safe_target(root: Path, target_file: str) -> tuple[Path | None, str]:
    relative = Path(target_file)
    if not target_file or relative.is_absolute() or ".." in relative.parts:
        return None, "target path must be repository-relative"
    target = root / relative
    if target.is_symlink():
        return None, "target file symlinks are not eligible"
    try:
        resolved = target.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None, "target path escapes the repository"
    if not resolved.is_file():
        return None, "target file is missing"
    return resolved, ""


def _replace_datetime_utcnow(source: str) -> tuple[str | None, str]:
    try:
        tree = ast.parse(source)
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (SyntaxError, tokenize.TokenError):
        return None, "target Python file could not be parsed"

    replacements = _utcnow_replacements(tokens, source)
    if not replacements:
        return None, "datetime.utcnow() is no longer present as an executable call"

    imports_timezone = False
    datetime_import_line: int | None = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module != "datetime":
            continue
        for alias in node.names:
            if alias.name == "timezone" and alias.asname is None:
                imports_timezone = True
            if alias.name == "datetime" and alias.asname is None and node.lineno == node.end_lineno:
                datetime_import_line = node.lineno

    if not imports_timezone:
        if datetime_import_line is None:
            return None, "a simple `from datetime import datetime` statement is required"
        import_replacement = _timezone_import_replacement(source, datetime_import_line)
        if import_replacement is None:
            return None, "the datetime import is not simple enough for a deterministic edit"
        replacements.append(import_replacement)

    patched = source
    for start, end, replacement in sorted(replacements, reverse=True):
        patched = patched[:start] + replacement + patched[end:]
    try:
        ast.parse(patched)
    except SyntaxError:
        return None, "the deterministic transformation did not produce valid Python"
    return patched, ""


def _utcnow_replacements(tokens: list[tokenize.TokenInfo], source: str) -> list[tuple[int, int, str]]:
    offsets = _line_offsets(source)
    replacements: list[tuple[int, int, str]] = []
    expected = ["datetime", ".", "utcnow", "(", ")"]
    for index in range(len(tokens) - len(expected) + 1):
        window = tokens[index : index + len(expected)]
        if [token.string for token in window] != expected:
            continue
        start = offsets[window[0].start[0] - 1] + window[0].start[1]
        end = offsets[window[-1].end[0] - 1] + window[-1].end[1]
        replacements.append((start, end, "datetime.now(timezone.utc)"))
    return replacements


def _timezone_import_replacement(source: str, line_number: int) -> tuple[int, int, str] | None:
    lines = source.splitlines(keepends=True)
    line = lines[line_number - 1]
    body = line.removesuffix("\n")
    match = re.fullmatch(r"(\s*)from datetime import ([A-Za-z_, ]+)(\s*(?:#.*)?)", body)
    if match is None:
        return None
    names = [name.strip() for name in match.group(2).split(",")]
    if "datetime" not in names or "timezone" in names:
        return None
    replacement = f"{match.group(1)}from datetime import {match.group(2).rstrip()}, timezone{match.group(3)}"
    start = sum(len(item) for item in lines[: line_number - 1])
    return start, start + len(body), replacement


def _line_offsets(source: str) -> list[int]:
    offsets = [0]
    for line in source.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def _unified_diff(target_file: str, source: str, patched: str) -> str:
    return "".join(
        difflib.unified_diff(
            source.splitlines(keepends=True),
            patched.splitlines(keepends=True),
            fromfile=f"a/{target_file}",
            tofile=f"b/{target_file}",
        )
    )


def _rollback_text(target_file: str, patch_name: str, source_hash: str) -> str:
    return f"""# Guarded Patch Rollback

- Target: `{target_file}`
- Original SHA-256: `{source_hash}`
- Patch artifact: `{patch_name}`

MycoPatch did not apply this draft. If a maintainer applies it manually, review the
resulting diff and tests first. A Git-based rollback can use:

```bash
git apply -R .myco/reports/patches/{patch_name}
```
"""


def _write_guarded_patch_report(
    report_path: Path,
    drafts: list[GuardedPatchDraft],
    rejected: list[str],
) -> None:
    lines = [
        "# Guarded Patch Drafts",
        "",
        f"- Timestamp: {utc_now().isoformat()}",
        "- Source files modified by MycoPatch: no",
        "- Evidence boundary: aggressive static-marker failures are not behavioral proof",
        "",
    ]
    for draft in drafts:
        lines.extend(
            [
                f"## {draft.target_file}",
                "",
                f"- Patch: `{draft.patch_path}`",
                f"- Rollback: `{draft.rollback_path}`",
                f"- Original SHA-256: `{draft.source_sha256}`",
                f"- Transformation: {draft.transformation}",
                f"- Evidence level: {draft.evidence_level}",
                "- Required review: inspect the diff, replace the static marker with a behavioral regression test, then run the project suite.",
                "",
            ]
        )
    if rejected:
        lines.extend(["## Ineligible Failures", ""])
        lines.extend(f"- {reason}" for reason in rejected)
        lines.append("")
    if not drafts and not rejected:
        lines.extend(["No failed probes are recorded.", ""])
    report_path.write_text("\n".join(lines), encoding="utf-8")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return slug[:80] or "target"
