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
        f"- Repo path: {scan.repo_root}",
        f"- Python files: {scan.python_file_count}",
        f"- Test files: {scan.test_file_count}",
        f"- Framework hints: {', '.join(scan.framework_hints) if scan.framework_hints else 'none detected'}",
        "",
        "## Top Risks",
        "",
    ]
    if risks:
        for risk in risks[:10]:
            lines.extend(
                [
                    f"### {risk.file_path}",
                    "",
                    f"- Risk type: {risk.risk_type}",
                    f"- Score: {risk.score}",
                    f"- Reason: {risk.reason}",
                    "- Evidence:",
                ]
            )
            lines.extend(f"  - `{item}`" for item in risk.evidence[:6])
            lines.append("")
    else:
        lines.extend(["No clear timezone/date-boundary risks detected.", ""])

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
            "`myco hunt --budget 30000`",
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
    probe_files = list(get_paths(repo_root).generated_tests.glob("test_myco_*.py"))
    return {
        "memory_events": len(events),
        "probes_generated": len(probe_files),
        "passed_probes": counts.get("probe_passed", 0),
        "failed_probes": counts.get("probe_failed", 0),
        "inconclusive_probes": counts.get("probe_inconclusive", 0)
        + counts.get("probe_skipped", 0)
        + counts.get("probe_blocked", 0),
        "cost": costs,
    }

