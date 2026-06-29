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
    if "datetime.utcnow" in lowered or "date.today" in lowered or "datetime.now" in lowered:
        ideas.append("Review UTC/local midnight, DST transition, month-end, and leap-day cases.")
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
    if "date.today" in lowered or "datetime.now" in lowered:
        return (
            "Inject a clock or date provider and test boundary behavior around local and UTC dates."
        )
    return (
        "Review the failing probe evidence, confirm intended behavior, and add a regression test before applying a manual fix."
    )

