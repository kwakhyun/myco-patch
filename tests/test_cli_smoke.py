import json

from typer.testing import CliRunner

from mycopatch.cli import app
from mycopatch.core.memory import read_memory_events


def test_cli_smoke_init_scan_hunt_report_patch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "billing.py").write_text(
        "from datetime import datetime\n"
        "def subscription_expires():\n"
        "    return datetime.utcnow()\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    init_result = runner.invoke(app, ["init"])
    scan_result = runner.invoke(app, ["scan"])
    hunt_result = runner.invoke(app, ["hunt", "--budget", "30000"])
    report_result = runner.invoke(app, ["report"])
    patch_result = runner.invoke(app, ["patch"])

    assert init_result.exit_code == 0, init_result.output
    assert scan_result.exit_code == 0, scan_result.output
    assert hunt_result.exit_code == 0, hunt_result.output
    assert report_result.exit_code == 0, report_result.output
    assert patch_result.exit_code == 0, patch_result.output
    weather_path = tmp_path / ".myco" / "reports" / "repo_weather.md"
    assert weather_path.exists()
    weather = weather_path.read_text(encoding="utf-8")
    assert "- Repo path: ." in weather
    assert "- Events: 1" in weather
    probe_paths = list((tmp_path / ".myco" / "probes" / "generated_tests").glob("test_myco_timezone_boundary_*.py"))
    assert probe_paths
    assert str(tmp_path) not in probe_paths[0].read_text(encoding="utf-8")
    assert (tmp_path / ".myco" / "reports" / "patch_recommendations.md").exists()

    generated_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / ".myco").rglob("*")
        if path.is_file() and path.suffix in {".md", ".jsonl", ".py"}
    )
    assert str(tmp_path) not in generated_text
    assert "<repo-root>" in generated_text

    for jsonl_path in (tmp_path / ".myco").rglob("*.jsonl"):
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                json.loads(line)


def test_cli_init_is_idempotent_without_duplicate_memory_event(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    first = runner.invoke(app, ["init"])
    second = runner.invoke(app, ["init"])

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert "already initialized" in second.output
    events = read_memory_events(tmp_path)
    assert [event.event_type for event in events].count("repo_initialized") == 1


def test_cli_missing_init_message_points_to_current_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(app, ["scan"])

    assert result.exit_code == 1
    assert "current directory" in result.output
    assert tmp_path.name in result.output
    assert "myco init" in result.output


def test_cli_aggressive_hunt_records_reproducible_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source_path = tmp_path / "billing.py"
    source_text = (
        "from datetime import datetime\n"
        "def subscription_expires():\n"
        "    return datetime.utcnow()\n"
    )
    source_path.write_text(source_text, encoding="utf-8")
    runner = CliRunner()

    assert runner.invoke(app, ["init"]).exit_code == 0
    result = runner.invoke(app, ["hunt", "--mode", "aggressive"])

    assert result.exit_code == 0, result.output
    assert "Probe failed reproducibly" in result.output
    assert "Aggressive probe report" in result.output
    assert source_path.read_text(encoding="utf-8") == source_text
    assert (tmp_path / ".myco" / "probes" / "generated_tests" / "test_myco_timezone_boundary_billing_py_aggressive.py").exists()
    assert (tmp_path / ".myco" / "probes" / "generated_tests" / "test_myco_timezone_boundary_billing_py_aggressive.md").exists()
    events = read_memory_events(tmp_path)
    assert any(event.event_type == "probe_failed" for event in events)
