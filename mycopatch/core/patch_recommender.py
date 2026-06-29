from __future__ import annotations

from pathlib import Path

from mycopatch.core.memory import append_memory_event, read_memory_events
from mycopatch.core.models import PatchRecommendation, utc_now
from mycopatch.core.paths import get_paths
from mycopatch.providers.base import BaseModelProvider
from mycopatch.providers.service import invoke_model_provider


FIX_STRATEGY = (
    "Prefer timezone-aware datetimes. Inject a clock where practical, use "
    "datetime.now(timezone.utc) for UTC timestamps, avoid datetime.utcnow(), "
    "and add regression tests around UTC/local midnight, DST transitions, "
    "month-end, and leap-day behavior."
)


def create_patch_recommendations(
    repo_root: Path | str,
    provider: BaseModelProvider | None = None,
) -> list[PatchRecommendation]:
    events = read_memory_events(repo_root)
    failures = [event for event in events if event.event_type == "probe_failed"]
    recommendations: list[PatchRecommendation] = []

    for event in failures:
        probe = event.payload.get("probe", {})
        result = event.payload.get("result", {})
        evidence = list(probe.get("evidence") or result.get("evidence") or [])
        failure_summary = invoke_model_provider(
            repo_root,
            task="summarize_failure_logs",
            prompt=_failure_summary_prompt(probe, result, evidence),
            provider=provider,
        )
        draft = invoke_model_provider(
            repo_root,
            task="draft_patch_recommendation",
            prompt=_patch_draft_prompt(probe, result, evidence, failure_summary.text),
            provider=provider,
        )
        recommendation = PatchRecommendation(
            suspected_file=probe.get("target_file", "unknown"),
            suspected_pattern=_suspected_pattern(evidence),
            evidence=evidence,
            generated_probe_path=probe.get("path", result.get("probe_path", "unknown")),
            suggested_manual_fix_strategy=draft.text or FIX_STRATEGY,
            failure_summary=failure_summary.text,
            provider_name=draft.provider_name,
        )
        recommendations.append(recommendation)

    write_patch_recommendation_report(repo_root, recommendations)
    if recommendations:
        append_memory_event(
            repo_root,
            "patch_recommendation_created",
            {"count": len(recommendations)},
        )
    return recommendations


def write_patch_recommendation_report(
    repo_root: Path | str,
    recommendations: list[PatchRecommendation],
) -> Path:
    paths = get_paths(repo_root)
    paths.reports.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Patch Recommendations",
        "",
        f"- Timestamp: {utc_now().isoformat()}",
        "",
    ]
    if not recommendations:
        lines.extend(
            [
                "No reproducible probe failures are currently recorded.",
                "",
                "Run `myco hunt --budget 30000` after adding focused spores or converting risk markers into failing regression tests.",
                "",
            ]
        )
    for index, recommendation in enumerate(recommendations, start=1):
        lines.extend(
            [
                f"## Recommendation {index}",
                "",
                f"- Suspected file: `{recommendation.suspected_file}`",
                f"- Suspected pattern: `{recommendation.suspected_pattern}`",
                f"- Generated probe: `{recommendation.generated_probe_path}`",
                f"- Advisory provider: `{recommendation.provider_name}`",
                f"- Failure summary: {recommendation.failure_summary}",
                f"- Strategy: {recommendation.suggested_manual_fix_strategy}",
                "- Evidence:",
            ]
        )
        lines.extend(f"  - `{item}`" for item in recommendation.evidence[:8])
        lines.append("")
    paths.patch_recommendations.write_text("\n".join(lines), encoding="utf-8")
    return paths.patch_recommendations


def _suspected_pattern(evidence: list[str]) -> str:
    text = "\n".join(evidence)
    for pattern in ["datetime.utcnow", "date.today", "datetime.now", "datetime("]:
        if pattern in text:
            return pattern
    return "timezone/date boundary behavior"


def _failure_summary_prompt(probe: dict, result: dict, evidence: list[str]) -> str:
    return "\n".join(
        [
            "Summarize this MycoPatch probe failure. Do not suggest a source patch.",
            f"Probe path: {probe.get('path', result.get('probe_path', 'unknown'))}",
            f"Target file: {probe.get('target_file', 'unknown')}",
            "Evidence:",
            *evidence[:12],
            "stdout:",
            str(result.get("stdout", ""))[:4000],
            "stderr:",
            str(result.get("stderr", ""))[:2000],
        ]
    )


def _patch_draft_prompt(
    probe: dict,
    result: dict,
    evidence: list[str],
    failure_summary: str,
) -> str:
    return "\n".join(
        [
            "Draft manual patch recommendation text for a MycoPatch report.",
            "Do not write a direct source-code patch.",
            f"Target file: {probe.get('target_file', 'unknown')}",
            f"Probe path: {probe.get('path', result.get('probe_path', 'unknown'))}",
            f"Failure summary: {failure_summary}",
            "Evidence:",
            *evidence[:12],
            f"Fallback strategy: {FIX_STRATEGY}",
        ]
    )
