from __future__ import annotations

from mycopatch.core.models import FileFinding, RepoScanResult, RiskFinding
from mycopatch.core.repo_scanner import TIME_KEYWORDS


def map_timezone_risks(scan: RepoScanResult) -> list[RiskFinding]:
    test_roots = {
        finding.path
        for finding in scan.python_files
        if finding.is_test_file
    }
    risks = [
        _risk_for_file(finding, test_roots)
        for finding in scan.python_files
        if _has_timezone_signal(finding)
    ]
    return sorted(
        (risk for risk in risks if risk.score > 0),
        key=lambda risk: (-risk.score, risk.file_path),
    )


def _risk_for_file(finding: FileFinding, test_files: set[str]) -> RiskFinding:
    score = 0
    reasons: list[str] = []

    if finding.imports_datetime:
        score += 10
        reasons.append("imports datetime")
    if finding.uses_datetime_now:
        score += 25
        reasons.append("uses datetime.now")
    if finding.uses_datetime_utcnow:
        score += 35
        reasons.append("uses datetime.utcnow")
    if finding.uses_date_today:
        score += 30
        reasons.append("uses date.today")
    if finding.uses_naive_datetime_construction:
        score += 20
        reasons.append("constructs datetime without tzinfo")
    if finding.contains_timezone_keywords:
        score += 20
        reasons.append("contains timezone-sensitive business keywords")
    if finding.is_test_file:
        score -= 20
        reasons.append("risk appears in a test file")
    else:
        score += 10
        reasons.append("risk appears in source code")
    if not _has_nearby_test(finding.path, test_files):
        score += 15
        reasons.append("no nearby test file detected")

    score = max(score, 0)
    return RiskFinding(
        file_path=finding.path,
        risk_type="timezone_boundary",
        score=score,
        evidence=finding.evidence,
        reason=", ".join(reasons),
    )


def _has_timezone_signal(finding: FileFinding) -> bool:
    return any(
        [
            finding.imports_datetime,
            finding.uses_datetime_now,
            finding.uses_datetime_utcnow,
            finding.uses_date_today,
            finding.uses_naive_datetime_construction,
            finding.contains_timezone_keywords,
            _path_has_keyword(finding.path),
        ]
    )


def _path_has_keyword(path: str) -> bool:
    lowered = path.lower()
    return any(keyword in lowered for keyword in TIME_KEYWORDS)


def _has_nearby_test(path: str, test_files: set[str]) -> bool:
    stem = path.rsplit("/", 1)[-1].removesuffix(".py")
    candidates = {
        f"test_{stem}.py",
        f"{stem}_test.py",
    }
    return any(test_file.endswith(candidate) for candidate in candidates for test_file in test_files)

