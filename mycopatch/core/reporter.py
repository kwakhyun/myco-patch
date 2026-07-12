from __future__ import annotations

from collections import Counter
from pathlib import Path

from mycopatch.core.cost import summarize_cost
from mycopatch.core.memory import read_memory_events, summarize_memory
from mycopatch.core.models import RepoScanResult, RiskFinding, utc_now
from mycopatch.core.paths import get_paths


def write_repo_weather(
    repo_root: Path | str,
    scan: RepoScanResult,
    risks: list[RiskFinding],
) -> Path:
    paths = get_paths(repo_root)
    paths.reports.mkdir(parents=True, exist_ok=True)
    cost = summarize_cost(repo_root)
    lines = [
        "# Repo Weather Report",
        "",
        f"- Timestamp: {utc_now().isoformat()}",
        "- Repo path: .",
        f"- Repo name: {Path(scan.repo_root).name}",
        f"- Python files: {scan.python_file_count}",
        f"- JS/TS files: {scan.js_ts_file_count}",
        f"- Test files: {scan.test_file_count}",
        f"- Framework hints: {', '.join(scan.framework_hints) if scan.framework_hints else 'none detected'}",
        "",
        "## Ecosystems",
        "",
    ]
    if scan.ecosystems:
        for ecosystem in scan.ecosystems:
            lines.extend(
                [
                    f"### {ecosystem.name}",
                    "",
                    f"- Language: {ecosystem.language}",
                    f"- Manifests: {', '.join(ecosystem.manifest_paths) if ecosystem.manifest_paths else 'source-only'}",
                    f"- Frameworks: {', '.join(hint.name for hint in ecosystem.framework_hints) if ecosystem.framework_hints else 'none detected'}",
                    f"- Test runner candidates: {', '.join(ecosystem.test_runner_candidates) if ecosystem.test_runner_candidates else 'none detected'}",
                    f"- Verification profiles: {', '.join(f'{profile.id} @ {profile.working_directory}' for profile in ecosystem.verification_profiles) if ecosystem.verification_profiles else 'none'}",
                    "",
                ]
            )
    else:
        lines.extend(["No supported ecosystems detected.", ""])

    lines.extend(
        [
        "## Top Risks",
        "",
        ]
    )
    if risks:
        for risk in risks[:10]:
            lines.extend(
                [
                    f"### {risk.file_path}",
                    "",
                    f"- Risk type: {risk.risk_type}",
                    f"- Language: {risk.language}",
                    f"- Score: {risk.score}",
                    f"- Confidence: {risk.confidence}",
                    f"- Nearby test detected: {'yes' if risk.nearby_test_detected else 'no'}",
                    f"- Reason: {risk.reason}",
                    "- Evidence:",
                ]
            )
            lines.extend(f"  - `{item}`" for item in risk.evidence[:6])
            lines.append("- Recommended human review steps:")
            lines.extend(f"  - {step}" for step in risk.recommended_review_steps[:5])
            lines.append("")
    else:
        lines.extend(["No clear MycoPatch risks detected.", ""])

    lines.extend(
        [
            "## Cost Summary",
            "",
            f"- Events: {cost['events']}",
            f"- Estimated input tokens: {cost['estimated_input_tokens']}",
            f"- Estimated output tokens: {cost['estimated_output_tokens']}",
            f"- Estimated cost USD: {cost['estimated_cost_usd']:.4f}",
            "",
            "## Recommended Next Command",
            "",
            "`myco risks` to inspect findings, then `myco hunt --budget 30000 --mode safe` or `myco hunt --budget 30000 --mode aggressive`.",
            "",
        ]
    )
    paths.repo_weather.write_text("\n".join(lines), encoding="utf-8")
    return paths.repo_weather


def write_immune_history(repo_root: Path | str) -> Path:
    paths = get_paths(repo_root)
    events = read_memory_events(repo_root)
    summary = summarize_memory(events)
    lines = [
        "# Immune History",
        "",
        f"- Timestamp: {utc_now().isoformat()}",
        f"- Total memory events: {len(events)}",
        "",
        "## Event Counts",
        "",
    ]
    if summary:
        lines.extend(f"- {event_type}: {count}" for event_type, count in sorted(summary.items()))
    else:
        lines.append("- No memory events recorded yet.")
    lines.extend(["", "## Recent Events", ""])
    for event in events[-20:]:
        lines.append(f"- {event.created_at.isoformat()} `{event.event_type}`")
    paths.immune_history.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return paths.immune_history


def build_console_report(repo_root: Path | str) -> dict[str, object]:
    events = read_memory_events(repo_root)
    counts: Counter[str] = summarize_memory(events)
    costs = summarize_cost(repo_root)
    generated_tests = get_paths(repo_root).generated_tests
    probe_files = [
        *generated_tests.glob("test_myco_*.py"),
        *generated_tests.glob("test_myco_*.mjs"),
    ]
    return {
        "memory_events": len(events),
        "probes_generated": counts.get("probe_generated", 0),
        "probe_files": len(probe_files),
        "passed_probes": counts.get("probe_passed", 0),
        "failed_probes": counts.get("probe_failed", 0),
        "inconclusive_probes": counts.get("probe_inconclusive", 0)
        + counts.get("probe_skipped", 0)
        + counts.get("probe_blocked", 0),
        "ecosystems_detected": counts.get("ecosystems_detected", 0),
        "verification_passed": counts.get("verification_passed", 0),
        "verification_failed": counts.get("verification_failed", 0),
        "verification_skipped": counts.get("verification_skipped", 0),
        "verification_blocked": counts.get("verification_blocked", 0),
        "verification_dry_run": counts.get("verification_dry_run", 0),
        "patch_drafts_created": counts.get("patch_draft_created", 0),
        "patch_drafts_ineligible": counts.get("patch_draft_ineligible", 0),
        "cost": costs,
    }
