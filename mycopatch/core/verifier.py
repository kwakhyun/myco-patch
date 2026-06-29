from __future__ import annotations

import shutil
from pathlib import Path

from mycopatch.core.models import Probe, ProbeResult
from mycopatch.sandbox.runner import run_command


def verify_probe(repo_root: Path | str, probe: Probe, timeout_seconds: int = 60) -> ProbeResult:
    root = Path(repo_root).resolve()
    probe_path = root / probe.path

    if not probe_path.exists():
        return ProbeResult(
            probe_id=probe.id,
            probe_path=probe.path,
            status="inconclusive",
            evidence=["Generated probe file is missing."],
        )

    if shutil.which("pytest") is None:
        return ProbeResult(
            probe_id=probe.id,
            probe_path=probe.path,
            status="skipped",
            evidence=["pytest is not available on PATH."],
        )

    result = run_command(["pytest", probe.path], cwd=root, timeout_seconds=timeout_seconds)
    if not result.allowed:
        return ProbeResult(
            probe_id=probe.id,
            probe_path=probe.path,
            status="blocked",
            stderr=result.stderr,
            evidence=[result.blocked_reason or "Command blocked by policy."],
        )

    status = "passed" if result.return_code == 0 else "failed"
    return ProbeResult(
        probe_id=probe.id,
        probe_path=probe.path,
        status=status,
        return_code=result.return_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_seconds=result.duration_seconds,
        evidence=[f"pytest return code: {result.return_code}"],
    )

