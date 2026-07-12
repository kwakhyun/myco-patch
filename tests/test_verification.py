from mycopatch.core.models import EcosystemFinding, VerificationProfile
from mycopatch.core.verification import select_verification_profiles, verify_profile


def test_select_verification_profiles_is_deterministic():
    ecosystems = [
        EcosystemFinding(
            name="go",
            language="Go",
            verification_profiles=[
                VerificationProfile(id="go-test", ecosystem="go", command=["go", "test", "./..."], description="Go tests")
            ],
        ),
        EcosystemFinding(
            name="python",
            language="Python",
            verification_profiles=[
                VerificationProfile(id="python-pytest", ecosystem="python", command=["pytest"], description="Pytest")
            ],
        ),
    ]

    profiles = select_verification_profiles(ecosystems)

    assert [profile.id for profile in profiles] == ["go-test", "python-pytest"]
    assert select_verification_profiles(ecosystems, ecosystem_name="go")[0].id == "go-test"
    assert select_verification_profiles(ecosystems, profile_id="python-pytest")[0].ecosystem == "python"


def test_verify_profile_dry_run_and_explicit_allow_gate(tmp_path):
    profile = VerificationProfile(id="go-test", ecosystem="go", command=["go", "test", "./..."], description="Go tests")

    dry_run = verify_profile(tmp_path, profile)
    blocked = verify_profile(tmp_path, profile, run=True)

    assert dry_run.status == "dry_run"
    assert blocked.status == "blocked"
    assert "--allow-project-tests" in blocked.evidence[0]


def test_verify_profile_skips_when_tool_missing(tmp_path, monkeypatch):
    profile = VerificationProfile(id="go-test", ecosystem="go", command=["go", "test", "./..."], description="Go tests")
    monkeypatch.setattr("mycopatch.core.verification.shutil.which", lambda executable: None)

    result = verify_profile(tmp_path, profile, run=True, allow_project_tests=True)

    assert result.status == "skipped"
    assert result.evidence == ["go is not available."]


def test_verify_profile_runs_allowed_command_and_sanitizes_output(tmp_path, monkeypatch):
    workdir = tmp_path / "services" / "billing"
    workdir.mkdir(parents=True)
    profile = VerificationProfile(
        id="go-test",
        ecosystem="go",
        command=["go", "test", "./..."],
        description="Go tests",
        working_directory="services/billing",
    )

    def fake_which(executable):
        return "/usr/bin/go"

    def fake_run_command(command, cwd, timeout_seconds, allow_project_tests=False, environment=None):
        from mycopatch.core.models import CommandResult

        assert cwd == workdir
        assert environment["MYCOPATCH_OFFLINE"] == "1"
        assert environment["GOPROXY"] == "off"
        return CommandResult(
            command=command,
            allowed=True,
            return_code=1,
            stdout=f"failure in {tmp_path}/billing.go",
            stderr=f"{tmp_path}/billing.go: bad date",
            duration_seconds=0.01,
        )

    monkeypatch.setattr("mycopatch.core.verification.shutil.which", fake_which)
    monkeypatch.setattr("mycopatch.core.verification.run_command", fake_run_command)

    result = verify_profile(tmp_path, profile, run=True, allow_project_tests=True)

    assert result.status == "failed"
    assert "<repo-root>" in result.stdout
    assert "<repo-root>" in result.stderr
    assert str(tmp_path) not in result.stdout
    assert str(tmp_path) not in result.stderr
    assert result.working_directory == "services/billing"


def test_verify_profile_blocks_working_directory_escape(tmp_path):
    profile = VerificationProfile(
        id="go-test",
        ecosystem="go",
        command=["go", "test", "./..."],
        description="Go tests",
        working_directory="../outside",
    )

    result = verify_profile(tmp_path, profile, run=True, allow_project_tests=True)

    assert result.status == "blocked"
    assert "inside the repository" in result.evidence[0]
