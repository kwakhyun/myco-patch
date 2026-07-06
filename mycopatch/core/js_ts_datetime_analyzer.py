from __future__ import annotations

import re

from mycopatch.core.models import EvidenceItem


DATE_ONLY_STRING_RE = re.compile(
    r"""new\s+Date\s*\(\s*['"]\d{4}-\d{2}-\d{2}['"]\s*\)"""
)
NEW_DATE_RE = re.compile(r"\bnew\s+Date\s*\(")
DATE_NOW_RE = re.compile(r"\bDate\s*\.\s*now\s*\(")
DATE_PARSE_RE = re.compile(r"\bDate\s*\.\s*parse\s*\(")
LOCAL_ACCESSOR_RE = re.compile(
    r"\.(getDate|getMonth|getFullYear|getHours|getMinutes|getSeconds|setDate|setMonth|setFullYear|setHours|setMinutes|setSeconds)\s*\("
)


def analyze_js_ts_datetime_risks(source: str) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    seen: set[tuple[int, str]] = set()
    for line_number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        for pattern, kind in _patterns_for_line(stripped):
            key = (line_number, pattern)
            if key in seen:
                continue
            seen.add(key)
            evidence.append(
                EvidenceItem(
                    line_number=line_number,
                    pattern=pattern,
                    snippet=stripped[:180],
                    kind=kind,
                )
            )
    return evidence


def _patterns_for_line(line: str) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    if DATE_ONLY_STRING_RE.search(line):
        matches.append(('new Date("YYYY-MM-DD")', "js_date_call"))
    elif NEW_DATE_RE.search(line):
        matches.append(("new Date()", "js_date_call"))

    if DATE_NOW_RE.search(line):
        matches.append(("Date.now()", "js_date_call"))
    if DATE_PARSE_RE.search(line):
        matches.append(("Date.parse(...)", "js_date_call"))
    accessor = LOCAL_ACCESSOR_RE.search(line)
    if accessor:
        matches.append((f"{accessor.group(1)}()", "js_date_accessor"))
    return matches
