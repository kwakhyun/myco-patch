from __future__ import annotations

import shutil
from pathlib import Path

from mycopatch.core.models import (
    EcosystemFinding,
    VerificationProfile,
    VerificationResult,
)
from mycopatch.sandbox.runner import run_command


def select_verification_profiles(
    ecosystems: list[EcosystemFinding],
    ecosystem_name: str = "all",
    profile_id: str | None = None,
) -> list[VerificationProfile]:
    profiles: list[VerificationProfile] = []
    for ecosystem in ecosystems:
        if ecosystem_name != "all" and ecosystem.name != ecosystem_name:
            continue
        for profile in ecosystem.verification_profiles:
            if profile_id is None or profile.id == profile_id:
                profiles.append(profile)
    return sorted(profiles, key=lambda item: (item.ecosystem, item.id))


def verify_profile(
    repo_root: Path | str,
    profile: VerificationProfile,
    *,
    run: bool = False,
    allow_project_tests: bool = False,
    timeout_seconds: int | None = None,
) -> VerificationResult:
    root = Path(repo_root).resolve()
    timeout = timeout_seconds or profile.default_timeout_seconds
    workdir = _resolve_working_directory(root, profile.working_directory)

    if workdir is None:
        return VerificationResult(
            profile_id=profile.id,
            ecosystem=profile.ecosystem,
            command=profile.command,
            working_directory=profile.working_directory,
            status="blocked",
            evidence=["Verification working directory must exist inside the repository."],
            stderr="Invalid verification working directory.",
        )

    if not run:
        return VerificationResult(
            profile_id=profile.id,
            ecosystem=profile.ecosystem,
            command=profile.command,
            working_directory=profile.working_directory,
            status="dry_run",
            evidence=["Dry run only. Add --run and --allow-project-tests to execute this project test profile."],
        )

    if profile.requires_explicit_allow and not allow_project_tests:
        return VerificationResult(
            profile_id=profile.id,
            ecosystem=profile.ecosystem,
            command=profile.command,
            working_directory=profile.working_directory,
            status="blocked",
            evidence=["Project test commands require --allow-project-tests or allow_project_test_commands = true."],
            stderr="Project test command execution was not explicitly allowed.",
        )

    missing_tool = _missing_tool(workdir, profile.command)
    if missing_tool is not None:
        return VerificationResult(
            profile_id=profile.id,
            ecosystem=profile.ecosystem,
            command=profile.command,
            working_directory=profile.working_directory,
            status="skipped",
            evidence=[f"{missing_tool} is not available."],
        )

    result = run_command(
        profile.command,
        cwd=workdir,
        timeout_seconds=timeout,
        allow_project_tests=allow_project_tests,
        environment=_offline_environment(profile.ecosystem),
    )
    if not result.allowed:
        return VerificationResult(
            profile_id=profile.id,
            ecosystem=profile.ecosystem,
            command=profile.command,
            working_directory=profile.working_directory,
            status="blocked",
            stderr=_sanitize_output(result.stderr, root),
            evidence=[result.blocked_reason or "Command blocked by policy."],
        )

    status = "passed" if result.return_code == 0 else "failed"
    return VerificationResult(
        profile_id=profile.id,
        ecosystem=profile.ecosystem,
        command=profile.command,
        working_directory=profile.working_directory,
        status=status,
        return_code=result.return_code,
        stdout=_sanitize_output(result.stdout, root),
        stderr=_sanitize_output(result.stderr, root),
        duration_seconds=result.duration_seconds,
        evidence=[f"return code: {result.return_code}", "MycoPatch offline environment controls were applied."],
    )


def _missing_tool(root: Path, command: list[str]) -> str | None:
    if not command:
        return "command"

    executable = command[0]
    if "/" in executable:
        return None if (root / executable).exists() else executable
    return None if shutil.which(executable) is not None else executable


def _resolve_working_directory(root: Path, value: str) -> Path | None:
    candidate = Path(value)
    if candidate.is_absolute():
        return None
    try:
        resolved = (root / candidate).resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    return resolved if resolved.is_dir() else None


def _offline_environment(ecosystem: str) -> dict[str, str]:
    environment = {
        "MYCOPATCH_OFFLINE": "1",
        "PIP_NO_INDEX": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "HTTP_PROXY": "http://127.0.0.1:9",
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "ALL_PROXY": "http://127.0.0.1:9",
        "NO_PROXY": "",
    }
    if ecosystem == "go":
        environment.update({"GOPROXY": "off", "GOSUMDB": "off"})
    elif ecosystem == "rust":
        environment["CARGO_NET_OFFLINE"] = "true"
    elif ecosystem == "dotnet":
        environment.update(
            {
                "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
                "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
            }
        )
    elif ecosystem == "php":
        environment["COMPOSER_DISABLE_NETWORK"] = "1"
    return environment


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
