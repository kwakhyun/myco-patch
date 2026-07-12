from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from mycopatch.core.models import CostEvent, MemoryEvent
from mycopatch.core.paths import get_paths


ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass(frozen=True)
class JsonlIssue:
    path: Path
    line_number: int
    error: str


def read_jsonl_models(path: Path, model: type[ModelT]) -> tuple[list[ModelT], list[JsonlIssue]]:
    records: list[ModelT] = []
    issues: list[JsonlIssue] = []
    if not path.exists():
        return records, issues

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(model.model_validate_json(line))
            except ValidationError as exc:
                issues.append(
                    JsonlIssue(
                        path=path,
                        line_number=line_number,
                        error=exc.errors(include_url=False)[0]["msg"],
                    )
                )
    return records, issues


def audit_repo_jsonl(repo_root: Path | str) -> list[JsonlIssue]:
    paths = get_paths(repo_root)
    issues: list[JsonlIssue] = []
    memory_files = sorted(paths.memory.glob("*.jsonl")) if paths.memory.exists() else []
    for path in memory_files:
        _, file_issues = read_jsonl_models(path, MemoryEvent)
        issues.extend(file_issues)
    _, cost_issues = read_jsonl_models(paths.cost_ledger, CostEvent)
    issues.extend(cost_issues)
    return issues
