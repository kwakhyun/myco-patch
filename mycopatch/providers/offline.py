from __future__ import annotations

from mycopatch.core.cost import estimate_tokens
from mycopatch.core.models import ModelRequest, ModelResponse
from mycopatch.providers.base import BaseModelProvider


class OfflineHeuristicProvider(BaseModelProvider):
    provider_name = "offline"
    requires_network = False

    def complete(self, request: ModelRequest) -> ModelResponse:
        text = _offline_response(request)
        return ModelResponse(
            text=text,
            provider_name=self.provider_name,
            model_name=self.config.model_name or "offline-heuristic",
            estimated_input_tokens=estimate_tokens(request.prompt),
            estimated_output_tokens=estimate_tokens(text),
            estimated_cost_usd=0.0,
            network_used=False,
        )


def _offline_response(request: ModelRequest) -> str:
    if request.task == "summarize_failure_logs":
        return _summarize_failure_logs(request.prompt)
    if request.task == "suggest_probe_ideas":
        return _suggest_probe_ideas(request.prompt)
    if request.task == "draft_patch_recommendation":
        return _draft_patch_recommendation(request.prompt)
    return "Offline heuristic provider has no response for this task."


def _summarize_failure_logs(prompt: str) -> str:
    interesting = [
        line.strip()
        for line in prompt.splitlines()
        if line.strip()
        and any(token in line.lower() for token in ["failed", "assert", "error", "risk", "pattern"])
    ]
    if not interesting:
        return "No concise failure signal was found in the captured logs."
    return "Key failure signal: " + " | ".join(interesting[:4])


def _suggest_probe_ideas(prompt: str) -> str:
    lowered = prompt.lower()
    ideas = [
        "Keep the generated probe file isolated under .myco/probes/generated_tests/.",
        "Use line-number evidence from static analysis as the probe metadata.",
    ]
    if any(
        pattern in lowered
        for pattern in ["datetime.utcnow", "date.today", "datetime.now", "new date", "date.now", "date.parse"]
    ):
        ideas.append("Review UTC/local midnight, DST transition, month-end, and leap-day cases.")
    if "mutable_default_argument" in lowered or "mutable default argument" in lowered:
        ideas.append("Use repeated-call tests to check whether state leaks across function calls.")
    if "broad_exception_swallow" in lowered or "broad exception swallowing" in lowered:
        ideas.append("Check whether failure evidence is preserved with logging, explicit errors, or re-raising.")
    if "no nearby test" in lowered:
        ideas.append("Create a nearby test file before changing production behavior.")
    return "\n".join(f"- {idea}" for idea in ideas)


def _draft_patch_recommendation(prompt: str) -> str:
    lowered = prompt.lower()
    if "datetime.utcnow" in lowered:
        return (
            "Prefer timezone-aware UTC timestamps, usually datetime.now(timezone.utc), "
            "and add focused regression tests before changing behavior."
        )
    if "mutable default argument" in lowered or "mutable_default_argument" in lowered:
        return (
            "Prefer None as the default value, allocate a fresh list/dict/set inside the function, "
            "and add a repeated-call regression test."
        )
    if "broad exception swallowing" in lowered or "broad_exception_swallow" in lowered:
        return (
            "Catch a narrower exception type and preserve failure evidence with logging, an explicit error result, "
            "or re-raising after cleanup."
        )
    if "new date" in lowered or "date.now" in lowered or "date.parse" in lowered:
        return (
            "Clarify whether the JavaScript Date logic should use UTC, user-local time, or an injected clock, "
            "then add focused boundary tests before changing behavior."
        )
    if "date.today" in lowered or "datetime.now" in lowered:
        return (
            "Inject a clock or date provider and test boundary behavior around local and UTC dates."
        )
    return (
        "Review the failing probe evidence, confirm intended behavior, and add a regression test before applying a manual fix."
    )
