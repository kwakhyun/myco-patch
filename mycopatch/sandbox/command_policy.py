from __future__ import annotations

from dataclasses import dataclass


PYTHON_EXECUTABLES = {"python", "python3"}

ALLOWED_GIT_SUBCOMMANDS = {
    ("git", "diff"),
    ("git", "status"),
}

DENIED_FRAGMENTS = [
    "rm -rf",
    "chmod 777",
    "mkfs",
    ":(){:|:&};:",
    "powershell invoke-webrequest",
    "env | grep",
    "cat .env",
    "docker run --privileged",
]

DENIED_EXECUTABLES = {
    "sudo",
    "curl",
    "wget",
    "ssh",
    "scp",
    "nc",
    "netcat",
    "chown",
    "dd",
    "mkfs",
    "printenv",
    "aws",
    "gcloud",
    "az",
    "kubectl",
    "npm",
    "npx",
    "yarn",
    "pnpm",
    "pip",
    "pip3",
    "composer",
}


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str


def check_command(command: list[str], allow_project_tests: bool = False) -> PolicyDecision:
    if not command:
        return PolicyDecision(False, "Empty command is not allowed.")

    executable = command[0].lower()
    if executable in DENIED_EXECUTABLES:
        return PolicyDecision(False, f"Blocked dangerous executable: {command[0]}")

    normalized = " ".join(command).lower()
    for fragment in DENIED_FRAGMENTS:
        if fragment.lower() in normalized:
            return PolicyDecision(False, f"Blocked dangerous command fragment: {fragment}")
    blocked_shape = _blocked_dependency_command(command)
    if blocked_shape is not None:
        return PolicyDecision(False, f"Blocked dependency installation or network-prone command: {blocked_shape}")

    if executable == "node":
        return _check_node_test_command(command, allow_project_tests=allow_project_tests)

    if executable == "pytest":
        return _check_pytest_command(command, allow_project_tests=allow_project_tests)

    project_test_decision = _check_project_test_command(
        command,
        allow_project_tests=allow_project_tests,
    )
    if project_test_decision is not None:
        return project_test_decision

    if executable in PYTHON_EXECUTABLES:
        if len(command) == 2 and command[1] in {"--version", "-V"}:
            return PolicyDecision(True, "Python version inspection is allowed by MycoPatch policy.")
        return PolicyDecision(
            False,
            "Python is limited to version inspection; arbitrary scripts, modules, and inline code are blocked.",
        )

    if len(command) >= 2 and (command[0], command[1]) in ALLOWED_GIT_SUBCOMMANDS:
        return PolicyDecision(True, "Git read-only inspection command is allowed.")

    return PolicyDecision(False, f"Command is not in the MycoPatch allowlist: {executable}")


def _check_node_test_command(command: list[str], allow_project_tests: bool) -> PolicyDecision:
    if len(command) == 2 and command[1] == "--test":
        return _project_test_decision(allow_project_tests, "Node project test profile is allowed by MycoPatch policy.")

    if len(command) != 3 or command[1] != "--test":
        return PolicyDecision(
            False,
            "Node is only allowed for generated MycoPatch probes: node --test .myco/probes/generated_tests/<probe>.mjs",
        )

    probe_path = command[2].replace("\\", "/")
    if (
        not probe_path.startswith(".myco/probes/generated_tests/")
        or not probe_path.endswith(".mjs")
        or ".." in probe_path.split("/")
    ):
        return PolicyDecision(
            False,
            "Node probe path must stay under .myco/probes/generated_tests/ and use .mjs.",
        )

    return PolicyDecision(True, "Generated node:test probe is allowed by MycoPatch policy.")


def _check_pytest_command(command: list[str], allow_project_tests: bool) -> PolicyDecision:
    if len(command) == 2:
        probe_path = command[1].replace("\\", "/")
        if (
            probe_path.startswith(".myco/probes/generated_tests/")
            and probe_path.endswith(".py")
            and ".." not in probe_path.split("/")
        ):
            return PolicyDecision(True, "Generated pytest probe is allowed by MycoPatch policy.")

    if len(command) == 1 or command[1:] in (["tests"], ["."]):
        return _project_test_decision(allow_project_tests, "Pytest project test profile is allowed by MycoPatch policy.")

    return PolicyDecision(False, f"Command is not an approved MycoPatch pytest profile: {' '.join(command)}")


def _check_project_test_command(command: list[str], allow_project_tests: bool) -> PolicyDecision | None:
    executable = command[0].lower()
    normalized = [part.lower() for part in command]
    allowed_shapes = [
        ["go", "test", "./..."],
        ["cargo", "test", "--offline"],
        ["mvn", "test", "-o"],
        ["gradle", "test", "--offline"],
        ["dotnet", "test", "--no-restore"],
        ["bundle", "exec", "rspec"],
        ["vendor/bin/phpunit"],
    ]
    if normalized in allowed_shapes:
        return _project_test_decision(
            allow_project_tests,
            f"{command[0]} project test profile is allowed by MycoPatch policy.",
        )

    if executable in {"go", "cargo", "mvn", "gradle", "dotnet", "bundle"} or executable.endswith("/phpunit"):
        return PolicyDecision(False, f"Command is not an approved MycoPatch project test profile: {' '.join(command)}")
    return None


def _project_test_decision(allow_project_tests: bool, allowed_reason: str) -> PolicyDecision:
    if allow_project_tests:
        return PolicyDecision(True, allowed_reason)
    return PolicyDecision(
        False,
        "Project test commands require explicit approval: use --allow-project-tests or allow_project_test_commands = true.",
    )


def _blocked_dependency_command(command: list[str]) -> str | None:
    normalized = [part.lower() for part in command]
    joined = " ".join(normalized)
    blocked_prefixes = [
        ["python", "-m", "pip", "install"],
        ["python3", "-m", "pip", "install"],
        ["go", "get"],
        ["go", "install"],
        ["cargo", "install"],
        ["cargo", "fetch"],
        ["cargo", "update"],
        ["bundle", "install"],
        ["mvn", "install"],
        ["dotnet", "restore"],
        ["dotnet", "add"],
        ["dotnet", "nuget"],
    ]
    for prefix in blocked_prefixes:
        if normalized[: len(prefix)] == prefix:
            return " ".join(prefix)
    if joined.startswith("mvn dependency:"):
        return "mvn dependency:*"
    if joined.startswith("gradle dependencies") or joined.startswith("gradle build"):
        return normalized[0] + " " + normalized[1]
    return None
