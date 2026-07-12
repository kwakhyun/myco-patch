import subprocess

from mycopatch.sandbox.runner import run_command


def test_runner_returns_auditable_result_when_process_cannot_start(tmp_path, monkeypatch):
    def fail_to_start(*args, **kwargs):
        raise OSError("executable disappeared")

    monkeypatch.setattr(subprocess, "run", fail_to_start)

    result = run_command(["pytest"], tmp_path, allow_project_tests=True)

    assert result.allowed
    assert result.return_code == 126
    assert "could not be started" in result.stderr


def test_runner_merges_explicit_environment(tmp_path, monkeypatch):
    captured = {}

    def capture_run(*args, **kwargs):
        captured.update(kwargs["env"])
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr(subprocess, "run", capture_run)

    result = run_command(
        ["pytest"],
        tmp_path,
        allow_project_tests=True,
        environment={"MYCOPATCH_OFFLINE": "1"},
    )

    assert result.return_code == 0
    assert captured["MYCOPATCH_OFFLINE"] == "1"
