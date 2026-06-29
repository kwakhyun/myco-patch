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

    if command[0] in ALLOWED_COMMANDS:
        return PolicyDecision(True, "Command is allowed by MycoPatch policy.")

    if len(command) >= 2 and (command[0], command[1]) in ALLOWED_GIT_SUBCOMMANDS:
        return PolicyDecision(True, "Git read-only inspection command is allowed.")

    return PolicyDecision(False, f"Command is not in the MycoPatch allowlist: {executable}")
