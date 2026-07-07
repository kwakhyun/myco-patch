from __future__ import annotations

from mycopatch.core.models import RiskFinding


def explain_risk(risk: RiskFinding) -> str:
    if risk.risk_type == "timezone_boundary":
        return _timezone_explanation(risk)
    if risk.risk_type == "mutable_default_argument":
        return (
            "Mutable default arguments are created once when the function is defined, "
            "not once per call. A list, dict, or set default can accidentally share "
            "state between separate calls."
        )
    if risk.risk_type == "broad_exception_swallow":
        return (
            "Broad exception handlers can hide real failures. When an Exception or "
            "bare except block only passes, returns None, or exits control flow, the "
            "caller may lose the evidence needed to debug production behavior."
        )
    return "MycoPatch found static evidence that deserves focused human review."


def _timezone_explanation(risk: RiskFinding) -> str:
    if risk.language in {"javascript", "typescript"}:
        return (
            "Date and timezone boundary logic can behave differently across UTC, "
            "server-local time, and user-local time. Date-only strings and local "
            "getters/setters are common sources of off-by-one-day bugs."
        )
    return (
        "Naive datetime and date-boundary logic can behave differently across UTC, "
        "server-local time, and user-local time. This often causes expiry, billing, "
        "deadline, and report ranges to shift around midnight or DST transitions."
    )
