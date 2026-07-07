from __future__ import annotations

import subprocess
import time
from pathlib import Path

from mycopatch.core.models import CommandResult
from mycopatch.sandbox.command_policy import check_command


def run_command(
    command: list[str],
    cwd: Path | str,
    timeout_seconds: int = 60,
    allow_project_tests: bool = False,
) -> CommandResult:
    decision = check_command(command, allow_project_tests=allow_project_tests)
    if not decision.allowed:
        return CommandResult(
            command=command,
            allowed=False,
            blocked_reason=decision.reason,
            stderr=decision.reason,
        )

    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=Path(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
        duration = time.monotonic() - started
        return CommandResult(
            command=command,
            allowed=True,
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_seconds=duration,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - started
        return CommandResult(
            command=command,
            allowed=True,
            return_code=124,
            stdout=exc.stdout or "",
            stderr=f"Command timed out after {timeout_seconds} seconds.",
            duration_seconds=duration,
        )
