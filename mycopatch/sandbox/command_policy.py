from __future__ import annotations

from dataclasses import dataclass


ALLOWED_COMMANDS = {
    "python",
    "python3",
    "pytest",
}

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
}


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str


def check_command(command: list[str]) -> PolicyDecision:
    if not command:
        return PolicyDecision(False, "Empty command is not allowed.")

    executable = command[0].lower()
    if executable in DENIED_EXECUTABLES:
        return PolicyDecision(False, f"Blocked dangerous executable: {command[0]}")

    normalized = " ".join(command).lower()
    for fragment in DENIED_FRAGMENTS:
        if fragment.lower() in normalized:
            return PolicyDecision(False, f"Blocked dangerous command fragment: {fragment}")

    if executable == "node":
        return _check_node_test_command(command)

    if command[0] in ALLOWED_COMMANDS:
        return PolicyDecision(True, "Command is allowed by MycoPatch policy.")

    if len(command) >= 2 and (command[0], command[1]) in ALLOWED_GIT_SUBCOMMANDS:
        return PolicyDecision(True, "Git read-only inspection command is allowed.")

    return PolicyDecision(False, f"Command is not in the MycoPatch allowlist: {executable}")


def _check_node_test_command(command: list[str]) -> PolicyDecision:
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
