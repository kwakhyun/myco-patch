from __future__ import annotations

from mycopatch.core.models import FileFinding, RepoScanResult, RiskFinding
from mycopatch.core.repo_scanner import TIME_KEYWORDS


def map_timezone_risks(scan: RepoScanResult) -> list[RiskFinding]:
    return map_repo_risks(scan)


def map_repo_risks(scan: RepoScanResult) -> list[RiskFinding]:
    test_roots = {
        finding.path
        for finding in scan.source_files
        if finding.is_test_file
    }
    risks: list[RiskFinding] = []
    for finding in scan.source_files:
        if _has_timezone_signal(finding):
            risks.append(_timezone_risk_for_file(finding, test_roots))
        if finding.uses_mutable_default_argument:
            risks.append(_python_bug_risk_for_file(finding, test_roots, "mutable_default_argument"))
        if finding.uses_broad_exception_swallow:
            risks.append(_python_bug_risk_for_file(finding, test_roots, "broad_exception_swallow"))
    return sorted(
        (risk for risk in risks if risk.score > 0),
        key=lambda risk: (-risk.score, risk.file_path),
    )


def _timezone_risk_for_file(finding: FileFinding, test_files: set[str]) -> RiskFinding:
    score = 0
    reasons: list[str] = []
    nearby_test_detected = _has_nearby_test(finding.path, test_files)

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
    if finding.uses_replace_tzinfo:
        score += 20
        reasons.append("uses replace(tzinfo=...)")
    if finding.uses_timezone_naive_comparison:
        score += 30
        reasons.append("compares timezone-sensitive values without clear timezone normalization")
    if finding.uses_js_new_date:
        score += 25
        reasons.append("uses new Date()")
    if finding.uses_js_date_now:
        score += 20
        reasons.append("uses Date.now()")
    if finding.uses_js_date_parse:
        score += 25
        reasons.append("uses Date.parse(...)")
    if finding.uses_js_date_string_constructor:
        score += 35
        reasons.append('uses new Date("YYYY-MM-DD")')
    if finding.uses_js_local_date_accessors:
        score += 20
        reasons.append("uses local Date getter/setter")
    if finding.contains_timezone_keywords:
        score += 20
        reasons.append("contains timezone-sensitive business keywords")
    if finding.is_test_file:
        score -= 20
        reasons.append("risk appears in a test file")
    else:
        score += 10
        reasons.append("risk appears in source code")
    if nearby_test_detected:
        reasons.append("nearby test file detected")
    else:
        score += 20
        reasons.append("no nearby test file detected")

    score = max(score, 0)
    return RiskFinding(
        file_path=finding.path,
        language=finding.language,
        risk_type="timezone_boundary",
        score=score,
        evidence=_evidence_lines(finding.datetime_evidence) or finding.evidence,
        evidence_items=finding.datetime_evidence,
        reason=", ".join(reasons),
        confidence=_confidence(score, finding),
        nearby_test_detected=nearby_test_detected,
        recommended_review_steps=_recommended_review_steps(finding, nearby_test_detected),
    )


def _python_bug_risk_for_file(
    finding: FileFinding,
    test_files: set[str],
    risk_type: str,
) -> RiskFinding:
    nearby_test_detected = _has_nearby_test(finding.path, test_files)
    evidence_items = [
        item for item in finding.bug_pattern_evidence if _risk_type_for_pattern(item.pattern) == risk_type
    ]
    score = 0
    reasons: list[str] = []

    if risk_type == "mutable_default_argument":
        score += 55
        reasons.append("defines a function with a mutable default argument")
    elif risk_type == "broad_exception_swallow":
        score += 60
        reasons.append("swallows a broad exception without preserving failure evidence")

    if finding.is_test_file:
        score -= 20
        reasons.append("risk appears in a test file")
    else:
        score += 10
        reasons.append("risk appears in source code")
    if nearby_test_detected:
        reasons.append("nearby test file detected")
    else:
        score += 10
        reasons.append("no nearby test file detected")

    score = max(score, 0)
    return RiskFinding(
        file_path=finding.path,
        language=finding.language,
        risk_type=risk_type,
        score=score,
        evidence=_evidence_lines(evidence_items),
        evidence_items=evidence_items,
        reason=", ".join(reasons),
        confidence=_bug_confidence(score, risk_type, finding),
        nearby_test_detected=nearby_test_detected,
        recommended_review_steps=_bug_review_steps(risk_type, nearby_test_detected),
    )


def _has_timezone_signal(finding: FileFinding) -> bool:
    return any(
        [
            finding.imports_datetime,
            finding.uses_datetime_now,
            finding.uses_datetime_utcnow,
            finding.uses_date_today,
            finding.uses_naive_datetime_construction,
            finding.uses_replace_tzinfo,
            finding.uses_timezone_naive_comparison,
            finding.uses_js_new_date,
            finding.uses_js_date_now,
            finding.uses_js_date_parse,
            finding.uses_js_date_string_constructor,
            finding.uses_js_local_date_accessors,
        ]
    )


def _path_has_keyword(path: str) -> bool:
    lowered = path.lower()
    return any(keyword in lowered for keyword in TIME_KEYWORDS)


def _has_nearby_test(path: str, test_files: set[str]) -> bool:
    parts = path.split("/")
    filename = parts[-1]
    stem = _stem_without_source_suffix(filename)
    parent_parts = parts[:-1]
    suffixes = _test_suffixes_for(filename)
    candidates = set()
    for suffix in suffixes:
        candidates.update(
            {
                f"test_{stem}{suffix}",
                f"{stem}_test{suffix}",
                f"{stem}.test{suffix}",
                f"{stem}.spec{suffix}",
                f"tests/test_{stem}{suffix}",
                f"tests/{stem}_test{suffix}",
                f"tests/{stem}.test{suffix}",
                f"tests/{stem}.spec{suffix}",
                f"__tests__/{stem}.test{suffix}",
                f"__tests__/test_{stem}{suffix}",
            }
        )
    if parent_parts:
        parent = "/".join(parent_parts)
        for suffix in suffixes:
            candidates.update(
                {
                    f"{parent}/test_{stem}{suffix}",
                    f"{parent}/{stem}_test{suffix}",
                    f"{parent}/{stem}.test{suffix}",
                    f"{parent}/{stem}.spec{suffix}",
                    f"tests/{parent}/test_{stem}{suffix}",
                    f"tests/{parent}/{stem}_test{suffix}",
                    f"tests/{parent}/{stem}.test{suffix}",
                    f"tests/{parent}/{stem}.spec{suffix}",
                    f"__tests__/{parent}/{stem}.test{suffix}",
                    f"__tests__/{parent}/test_{stem}{suffix}",
                }
            )
    return any(test_file == candidate or test_file.endswith(f"/{candidate}") for candidate in candidates for test_file in test_files)


def _confidence(score: int, finding: FileFinding) -> str:
    strong_patterns = sum(
        [
            finding.uses_datetime_utcnow,
            finding.uses_date_today,
            finding.uses_naive_datetime_construction,
            finding.uses_replace_tzinfo,
            finding.uses_timezone_naive_comparison,
            finding.uses_js_date_parse,
            finding.uses_js_date_string_constructor,
            finding.uses_js_local_date_accessors,
        ]
    )
    if score >= 90 and (strong_patterns >= 1 or finding.uses_js_new_date):
        return "high"
    if score >= 45 and (
        strong_patterns >= 1
        or finding.uses_datetime_now
        or finding.uses_js_date_now
        or finding.uses_js_new_date
    ):
        return "medium"
    return "low"


def _bug_confidence(score: int, risk_type: str, finding: FileFinding) -> str:
    if risk_type == "mutable_default_argument" and score >= 65 and not finding.is_test_file:
        return "high"
    if risk_type == "broad_exception_swallow" and score >= 70 and not finding.is_test_file:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def _recommended_review_steps(finding: FileFinding, nearby_test_detected: bool) -> list[str]:
    steps = [
        "Confirm the intended timezone boundary behavior with a maintainer.",
        "Add or review regression tests around UTC/local midnight, DST transitions, month-end, and leap-day behavior.",
    ]
    if finding.uses_datetime_utcnow:
        steps.append("Prefer datetime.now(timezone.utc) over datetime.utcnow() where UTC timestamps are intended.")
    if finding.uses_datetime_now or finding.uses_date_today:
        steps.append("Inject a clock or timezone-aware date provider for deterministic tests.")
    if finding.uses_replace_tzinfo:
        steps.append("Check whether replace(tzinfo=...) is incorrectly labeling local time instead of converting it.")
    if finding.uses_timezone_naive_comparison:
        steps.append("Normalize both sides of datetime comparisons before comparing.")
    if finding.language in {"javascript", "typescript"}:
        steps.append("Check whether Date values should use UTC methods or an injected clock.")
    if finding.uses_js_date_string_constructor:
        steps.append('Avoid ambiguous date-only parsing like new Date("YYYY-MM-DD"); parse with an explicit timezone or calendar rule.')
    if finding.uses_js_local_date_accessors:
        steps.append("Review local Date getters/setters against UTC and user-timezone requirements.")
    if not nearby_test_detected:
        steps.append("Create a nearby test file before changing production behavior.")
    return steps


def _bug_review_steps(risk_type: str, nearby_test_detected: bool) -> list[str]:
    if risk_type == "mutable_default_argument":
        steps = [
            "Confirm whether the default value is intended to be shared across calls.",
            "Prefer None as the default and create a new list, dict, or set inside the function.",
            "Add a regression test with two calls to the function to check state isolation.",
        ]
    elif risk_type == "broad_exception_swallow":
        steps = [
            "Confirm whether the exception should be handled at this layer.",
            "Catch a narrower exception type where possible.",
            "Preserve failure evidence by logging, returning an explicit error, or re-raising after cleanup.",
        ]
    else:
        steps = ["Confirm intended behavior and add a focused regression test."]
    if not nearby_test_detected:
        steps.append("Create a nearby test file before changing production behavior.")
    return steps


def _evidence_lines(items) -> list[str]:
    return [f"L{item.line_number}: {item.snippet}" for item in items]


def _risk_type_for_pattern(pattern: str) -> str | None:
    if pattern == "mutable default argument":
        return "mutable_default_argument"
    if pattern == "broad exception swallowing":
        return "broad_exception_swallow"
    return None


def _stem_without_source_suffix(filename: str) -> str:
    for suffix in [".tsx", ".jsx", ".mjs", ".cjs", ".ts", ".js", ".py"]:
        if filename.endswith(suffix):
            return filename[: -len(suffix)]
    return filename.rsplit(".", 1)[0]


def _test_suffixes_for(filename: str) -> set[str]:
    if filename.endswith(".py"):
        return {".py"}
    if filename.endswith((".ts", ".tsx")):
        return {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
    return {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
