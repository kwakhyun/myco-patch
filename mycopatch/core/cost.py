from __future__ import annotations

import json
from pathlib import Path

from mycopatch.core.models import CostEvent
from mycopatch.core.paths import get_paths


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4) if text else 0


def record_cost_event(
    repo_root: Path | str,
    *,
    input_text: str = "",
    output_text: str = "",
    budget_limit: int | None = None,
    notes: str = "",
) -> CostEvent:
    paths = get_paths(repo_root)
    paths.reports.mkdir(parents=True, exist_ok=True)
    event = CostEvent(
        estimated_input_tokens=estimate_tokens(input_text),
        estimated_output_tokens=estimate_tokens(output_text),
        estimated_cost_usd=0.0,
        budget_limit=budget_limit,
        notes=notes,
    )
    with paths.cost_ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event.json_dict(), sort_keys=True) + "\n")
    return event


def read_cost_events(repo_root: Path | str) -> list[CostEvent]:
    paths = get_paths(repo_root)
    if not paths.cost_ledger.exists():
        return []
    events: list[CostEvent] = []
    for line in paths.cost_ledger.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(CostEvent.model_validate_json(line))
    return events


def summarize_cost(repo_root: Path | str) -> dict[str, float | int]:
    events = read_cost_events(repo_root)
    return {
        "events": len(events),
        "estimated_input_tokens": sum(event.estimated_input_tokens for event in events),
        "estimated_output_tokens": sum(event.estimated_output_tokens for event in events),
        "estimated_cost_usd": sum(event.estimated_cost_usd for event in events),
    }

