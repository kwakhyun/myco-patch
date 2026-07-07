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

    if probe.test_runner == "pytest":
        command_name = "pytest"
        command = ["pytest", probe.path]
    elif probe.test_runner == "node-test":
        command_name = "node"
        command = ["node", "--test", probe.path]
    else:
        return ProbeResult(
            probe_id=probe.id,
            probe_path=probe.path,
            status="inconclusive",
            evidence=[f"Unsupported generated probe test runner: {probe.test_runner}"],
        )

    if shutil.which(command_name) is None:
        return ProbeResult(
            probe_id=probe.id,
            probe_path=probe.path,
            status="skipped",
            evidence=[f"{command_name} is not available on PATH."],
        )

    result = run_command(command, cwd=root, timeout_seconds=timeout_seconds)
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
        stdout=_sanitize_output(result.stdout, root),
        stderr=_sanitize_output(result.stderr, root),
        duration_seconds=result.duration_seconds,
        evidence=[f"{probe.test_runner} return code: {result.return_code}"],
    )


def _sanitize_output(text: str, repo_root: Path) -> str:
    if not text:
        return text

    replacements = {
        repo_root.as_posix(),
        str(repo_root),
        repo_root.resolve().as_posix(),
        str(repo_root.resolve()),
    }
    sanitized = text
    for value in sorted(replacements, key=len, reverse=True):
        if value:
            sanitized = sanitized.replace(value, "<repo-root>")
    return sanitized
