from mycopatch.sandbox.command_policy import check_command


def test_policy_allows_expected_commands():
    assert check_command(["python", "--version"]).allowed
    assert check_command(["pytest", "tests"]).allowed
    assert check_command(["git", "status"]).allowed
    assert check_command(["git", "diff"]).allowed


def test_policy_blocks_dangerous_commands():
    commands = [
        ["rm", "-rf", "/tmp/example"],
        ["sudo", "pytest"],
        ["curl", "https://example.com"],
        ["cat", ".env"],
        ["docker", "run", "--privileged", "image"],
        ["aws", "s3", "ls"],
    ]

    for command in commands:
        decision = check_command(command)
        assert not decision.allowed
        assert "Blocked" in decision.reason or "allowlist" in decision.reason


def test_policy_does_not_block_dangerous_names_inside_allowed_arguments():
    decision = check_command(["python", "azure_report.py"])

    assert decision.allowed
