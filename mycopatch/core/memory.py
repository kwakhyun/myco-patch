from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from mycopatch.core.models import MemoryEvent
from mycopatch.core.paths import get_paths


EVENT_FILE_MAP = {
    "probe_passed": "negative_results.jsonl",
    "probe_inconclusive": "negative_results.jsonl",
    "probe_skipped": "negative_results.jsonl",
    "probe_blocked": "negative_results.jsonl",
    "probe_failed": "failure_patterns.jsonl",
    "patch_recommendation_created": "accepted_patches.jsonl",
}


def append_memory_event(
    repo_root: Path | str,
    event_type: str,
    payload: dict,
    filename: str | None = None,
) -> MemoryEvent:
    paths = get_paths(repo_root)
    paths.memory.mkdir(parents=True, exist_ok=True)
    event = MemoryEvent(event_type=event_type, payload=payload)
    target_name = filename or EVENT_FILE_MAP.get(event_type, "failure_patterns.jsonl")
    target = paths.memory / target_name
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event.json_dict(), sort_keys=True) + "\n")
    return event


def read_memory_events(repo_root: Path | str) -> list[MemoryEvent]:
    paths = get_paths(repo_root)
    events: list[MemoryEvent] = []
    if not paths.memory.exists():
        return events
    for path in sorted(paths.memory.glob("*.jsonl")):
        events.extend(_read_jsonl_events(path))
    return sorted(events, key=lambda event: event.created_at)


def summarize_memory(events: Iterable[MemoryEvent]) -> Counter[str]:
    return Counter(event.event_type for event in events)


def _read_jsonl_events(path: Path) -> list[MemoryEvent]:
    events: list[MemoryEvent] = []
    if not path.exists():
        return events
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(MemoryEvent.model_validate_json(line))
    return events

