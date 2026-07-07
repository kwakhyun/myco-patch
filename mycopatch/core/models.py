from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


SCHEMA_VERSION = "0.6.0"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SerializableModel(BaseModel):
    def json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class EvidenceItem(SerializableModel):
    line_number: int
    pattern: str
    snippet: str
    kind: str


class FileFinding(SerializableModel):
    path: str
    language: Literal["python", "javascript", "typescript"] = "python"
    line_count: int
    imports_datetime: bool = False
    uses_datetime_now: bool = False
    uses_datetime_utcnow: bool = False
    uses_date_today: bool = False
    uses_naive_datetime_construction: bool = False
    uses_replace_tzinfo: bool = False
    uses_timezone_naive_comparison: bool = False
    uses_js_new_date: bool = False
    uses_js_date_now: bool = False
    uses_js_date_parse: bool = False
    uses_js_date_string_constructor: bool = False
    uses_js_local_date_accessors: bool = False
    contains_timezone_keywords: bool = False
    uses_mutable_default_argument: bool = False
    uses_broad_exception_swallow: bool = False
    is_test_file: bool = False
    evidence: list[str] = Field(default_factory=list)
    datetime_evidence: list[EvidenceItem] = Field(default_factory=list)
    bug_pattern_evidence: list[EvidenceItem] = Field(default_factory=list)


class RepoScanResult(SerializableModel):
    repo_root: str
    scanned_at: datetime = Field(default_factory=utc_now)
    python_files: list[FileFinding] = Field(default_factory=list)
    js_ts_files: list[FileFinding] = Field(default_factory=list)
    ecosystems: list["EcosystemFinding"] = Field(default_factory=list)
    ignored_dirs: list[str] = Field(default_factory=list)
    framework_hints: list[str] = Field(default_factory=list)

    @property
    def source_files(self) -> list[FileFinding]:
        return [*self.python_files, *self.js_ts_files]

    @property
    def python_file_count(self) -> int:
        return len(self.python_files)

    @property
    def js_ts_file_count(self) -> int:
        return len(self.js_ts_files)

    @property
    def source_file_count(self) -> int:
        return len(self.source_files)

    @property
    def test_file_count(self) -> int:
        return sum(1 for finding in self.source_files if finding.is_test_file)


class RiskFinding(SerializableModel):
    file_path: str
    language: Literal["python", "javascript", "typescript"] = "python"
    risk_type: str
    score: int
    evidence: list[str] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    reason: str
    confidence: Literal["low", "medium", "high"] = "low"
    nearby_test_detected: bool = False
    recommended_review_steps: list[str] = Field(default_factory=list)


class SporeProbeSpec(SerializableModel):
    type: str
    strategy: str


class SporeBudget(SerializableModel):
    max_input_tokens: int
    max_output_tokens: int
    max_runtime_seconds: int


class SporeSafety(SerializableModel):
    network: str
    write_paths: list[str] = Field(default_factory=list)


class SporeTriggers(SerializableModel):
    path_keywords: list[str] = Field(default_factory=list)
    code_patterns: list[str] = Field(default_factory=list)


class Spore(SerializableModel):
    name: str
    version: str
    language: str
    description: str
    risk_type: str
    triggers: SporeTriggers
    probe: SporeProbeSpec
    budget: SporeBudget
    safety: SporeSafety
    source: Literal["builtin", "local"] = "builtin"


class Probe(SerializableModel):
    id: str
    risk_type: str
    target_file: str
    path: str
    created_at: datetime = Field(default_factory=utc_now)
    evidence: list[str] = Field(default_factory=list)
    spore_name: str
    safe_default: bool = True
    mode: Literal["safe", "aggressive"] = "safe"
    test_runner: str = "pytest"
    explanation_path: str | None = None


class ProbeResult(SerializableModel):
    probe_id: str
    probe_path: str
    status: Literal["passed", "failed", "inconclusive", "skipped", "blocked"]
    return_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class FrameworkHint(SerializableModel):
    name: str
    ecosystem: str
    source: str
    confidence: Literal["low", "medium", "high"] = "medium"


class VerificationProfile(SerializableModel):
    id: str
    ecosystem: str
    command: list[str]
    description: str
    requires_explicit_allow: bool = True
    default_timeout_seconds: int = 120


class EcosystemFinding(SerializableModel):
    name: str
    language: str
    manifest_paths: list[str] = Field(default_factory=list)
    framework_hints: list[FrameworkHint] = Field(default_factory=list)
    test_runner_candidates: list[str] = Field(default_factory=list)
    verification_profiles: list[VerificationProfile] = Field(default_factory=list)


class VerificationResult(SerializableModel):
    profile_id: str
    ecosystem: str
    command: list[str]
    status: Literal["passed", "failed", "skipped", "blocked", "dry_run"]
    return_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class CostEvent(SerializableModel):
    event_type: str = "cost_recorded"
    task: str | None = None
    provider_name: str | None = None
    model_name: str = "offline-heuristic"
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    budget_limit: int | None = None
    created_at: datetime = Field(default_factory=utc_now)
    notes: str = ""


class MemoryEvent(SerializableModel):
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    schema_version: str = SCHEMA_VERSION


class PatchRecommendation(SerializableModel):
    suspected_file: str
    suspected_pattern: str
    evidence: list[str] = Field(default_factory=list)
    generated_probe_path: str
    suggested_manual_fix_strategy: str
    failure_summary: str = ""
    provider_name: str = "offline-heuristic"
    created_at: datetime = Field(default_factory=utc_now)


class ModelProviderConfig(SerializableModel):
    default_provider: Literal["offline", "openai-compatible", "local-http"] = "offline"
    model_name: str = "offline-heuristic"
    max_input_tokens: int = 6000
    max_output_tokens: int = 1200
    max_cost_usd: float = 0.0
    allow_network_for_model_provider: bool = False
    allow_project_test_commands: bool = False
    provider_base_url: str = ""
    api_key_env: str = "OPENAI_API_KEY"


class ModelRequest(SerializableModel):
    task: Literal[
        "summarize_failure_logs",
        "suggest_probe_ideas",
        "draft_patch_recommendation",
    ]
    prompt: str
    max_input_tokens: int
    max_output_tokens: int


class ModelResponse(SerializableModel):
    text: str
    provider_name: str
    model_name: str
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    network_used: bool = False


class CommandResult(SerializableModel):
    command: list[str]
    allowed: bool
    return_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    blocked_reason: str | None = None


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
