from mycopatch.sandbox.command_policy import check_command


def test_policy_allows_expected_commands():
    assert check_command(["node", "--test", ".myco/probes/generated_tests/test_probe.mjs"]).allowed
    assert check_command(["pytest", ".myco/probes/generated_tests/test_probe.py"]).allowed
    assert check_command(["python", "--version"]).allowed
    assert check_command(["python3", "-V"]).allowed
    assert check_command(["git", "status"]).allowed
    assert check_command(["git", "diff"]).allowed


def test_policy_requires_explicit_allow_for_project_test_profiles():
    project_commands = [
        ["pytest", "tests"],
        ["node", "--test"],
        ["go", "test", "./..."],
        ["cargo", "test", "--offline"],
        ["mvn", "test", "-o"],
        ["gradle", "test", "--offline"],
        ["dotnet", "test", "--no-restore"],
        ["bundle", "exec", "rspec"],
        ["vendor/bin/phpunit"],
    ]

    for command in project_commands:
        assert not check_command(command).allowed
        assert check_command(command, allow_project_tests=True).allowed


def test_policy_rejects_unapproved_project_test_shapes_even_with_allow():
    commands = [
        ["pytest", "--basetemp", "/tmp/example"],
        ["go", "test", "-exec", "sh"],
        ["cargo", "test"],
        ["dotnet", "test"],
    ]

    for command in commands:
        assert not check_command(command, allow_project_tests=True).allowed


def test_policy_blocks_arbitrary_python_execution():
    commands = [
        ["python", "-c", "import os; os.remove('target')"],
        ["python3", "script.py"],
        ["python", "-m", "http.server"],
    ]

    for command in commands:
        decision = check_command(command)
        assert not decision.allowed
        assert "arbitrary" in decision.reason


def test_policy_limits_node_to_generated_probe_tests():
    blocked_commands = [
        ["node", "-e", "console.log(process.env)"],
        ["node", "server.js"],
        ["node", "--test", "tests/example.test.mjs"],
        ["node", "--test", ".myco/probes/generated_tests/../escape.mjs"],
        ["node", "--test", ".myco/probes/generated_tests/test_probe.js"],
    ]

    for command in blocked_commands:
        decision = check_command(command)
        assert not decision.allowed
        assert "Node" in decision.reason


def test_policy_blocks_dangerous_commands():
    commands = [
        ["rm", "-rf", "/tmp/example"],
        ["sudo", "pytest"],
        ["curl", "https://example.com"],
        ["pip", "install", "package"],
        ["python", "-m", "pip", "install", "package"],
        ["cat", ".env"],
        ["docker", "run", "--privileged", "image"],
        ["aws", "s3", "ls"],
        ["env", "|", "grep", "TOKEN"],
        ["printenv"],
        ["powershell", "Invoke-WebRequest", "https://example.com"],
        ["kubectl", "get", "secrets"],
        ["npm", "test"],
        ["npx", "vitest"],
        ["yarn", "test"],
        ["pnpm", "test"],
        ["go", "get", "example.com/mod"],
        ["cargo", "install", "tool"],
        ["bundle", "install"],
        ["composer", "install"],
        ["dotnet", "restore"],
    ]

    for command in commands:
        decision = check_command(command)
        assert not decision.allowed
        assert "Blocked" in decision.reason or "allowlist" in decision.reason


def test_policy_does_not_block_dangerous_names_inside_allowed_arguments():
    decision = check_command(["git", "diff", "azure_report.py"])

    assert decision.allowed
