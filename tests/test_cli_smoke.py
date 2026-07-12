import json

from typer.testing import CliRunner

from mycopatch.cli import app
from mycopatch.core.memory import read_memory_events
from mycopatch.core.reporter import build_console_report


def test_cli_version():
    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == "0.7.0"


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
    ecosystems_result = runner.invoke(app, ["ecosystems", "--json"])
    verify_result = runner.invoke(app, ["verify", "--no-run"])
    hunt_result = runner.invoke(app, ["hunt", "--budget", "30000"])
    report_result = runner.invoke(app, ["report"])
    patch_result = runner.invoke(app, ["patch"])

    assert init_result.exit_code == 0, init_result.output
    assert scan_result.exit_code == 0, scan_result.output
    assert ecosystems_result.exit_code == 0, ecosystems_result.output
    assert verify_result.exit_code == 0, verify_result.output
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
    ecosystems_payload = json.loads(ecosystems_result.output)
    assert ecosystems_payload[0]["verification_profiles"][0]["id"] == "python-pytest"
    assert "dry_run" in verify_result.output

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


def test_cli_spores_list_works_without_init(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(app, ["spores", "list"])

    assert result.exit_code == 0, result.output
    assert "python-timezone-boundary" in result.output
    assert "js-ts-timezone-boundary" in result.output


def test_cli_scan_and_risks_json_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "billing.py").write_text(
        "from datetime import date\n"
        "def deadline():\n"
        "    return date.today()\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    assert runner.invoke(app, ["init"]).exit_code == 0
    scan_result = runner.invoke(app, ["scan", "--json"])
    risks_result = runner.invoke(app, ["risks", "--json"])

    assert scan_result.exit_code == 0, scan_result.output
    scan_payload = json.loads(scan_result.output)
    assert scan_payload["repo_path"] == "."
    assert scan_payload["python_files"] == 1
    assert scan_payload["risk_count"] == 1
    assert scan_payload["ecosystems"][0]["name"] == "python"
    assert scan_payload["report_path"] == ".myco/reports/repo_weather.md"
    assert str(tmp_path) not in scan_result.output

    assert risks_result.exit_code == 0, risks_result.output
    risks_payload = json.loads(risks_result.output)
    assert risks_payload[0]["file_path"] == "billing.py"
    assert risks_payload[0]["language"] == "python"


def test_cli_doctor_reports_invalid_config_and_hunt_exits_cleanly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "billing.py").write_text(
        "from datetime import datetime\n"
        "def expires():\n"
        "    return datetime.utcnow()\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    assert runner.invoke(app, ["init"]).exit_code == 0
    (tmp_path / ".myco" / "config.toml").write_text(
        'default_provider = "not-real"\n',
        encoding="utf-8",
    )

    doctor = runner.invoke(app, ["doctor"])
    hunt = runner.invoke(app, ["hunt"])

    assert doctor.exit_code == 0, doctor.output
    assert "config valid" in doctor.output
    assert "no:" in doctor.output
    assert hunt.exit_code == 1
    assert "Invalid MycoPatch config" in hunt.output
    assert "myco doctor" in hunt.output


def test_cli_hunt_dry_run_does_not_generate_probe(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "billing.ts").write_text(
        "export function due() {\n"
        "  return Date.now()\n"
        "}\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    assert runner.invoke(app, ["init"]).exit_code == 0
    result = runner.invoke(app, ["hunt", "--dry-run", "--language", "js-ts"])

    assert result.exit_code == 0, result.output
    assert "Dry run only" in result.output
    assert "billing.ts" in result.output
    assert not list((tmp_path / ".myco" / "probes" / "generated_tests").glob("test_myco_*"))


def test_cli_hunt_enforces_token_budget_before_generation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "billing.py").write_text(
        "from datetime import datetime\ndef expires():\n    return datetime.utcnow()\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    assert runner.invoke(app, ["init"]).exit_code == 0
    result = runner.invoke(app, ["hunt", "--budget", "1", "--no-run"])

    assert result.exit_code == 0, result.output
    assert "budget exhausted" in result.output
    assert not list((tmp_path / ".myco" / "probes" / "generated_tests").glob("test_myco_*"))


def test_cli_verify_returns_nonzero_when_project_tests_fail(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "test_failure.py").write_text("def test_failure():\n    assert False\n", encoding="utf-8")
    runner = CliRunner()

    assert runner.invoke(app, ["init"]).exit_code == 0
    result = runner.invoke(app, ["verify", "--run", "--allow-project-tests"])

    assert result.exit_code == 1
    assert "failed" in result.output


def test_cli_hunt_language_filter_generates_only_matching_probe(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "billing.py").write_text(
        "from datetime import datetime\n"
        "def expires():\n"
        "    return datetime.utcnow()\n",
        encoding="utf-8",
    )
    (tmp_path / "billing.ts").write_text(
        "export const due = Date.now()\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    assert runner.invoke(app, ["init"]).exit_code == 0
    result = runner.invoke(app, ["hunt", "--no-run", "--language", "python"])

    assert result.exit_code == 0, result.output
    generated = tmp_path / ".myco" / "probes" / "generated_tests"
    assert (generated / "test_myco_timezone_boundary_billing_py.py").exists()
    assert not (generated / "test_myco_js_timezone_boundary_billing_ts.mjs").exists()


def test_console_report_counts_generated_probes_from_memory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "billing.py").write_text(
        "from datetime import datetime\n"
        "def expires():\n"
        "    return datetime.utcnow()\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    assert runner.invoke(app, ["init"]).exit_code == 0
    assert runner.invoke(app, ["hunt", "--no-run"]).exit_code == 0
    probe_path = tmp_path / ".myco" / "probes" / "generated_tests" / "test_myco_timezone_boundary_billing_py.py"
    probe_path.unlink()

    report = build_console_report(tmp_path)

    assert report["probes_generated"] == 1
    assert report["probe_files"] == 0


def test_cli_explain_and_memory_commands(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "state.py").write_text(
        "def add_item(item, items=[]):\n"
        "    items.append(item)\n"
        "    return items\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    assert runner.invoke(app, ["init"]).exit_code == 0
    assert runner.invoke(app, ["scan"]).exit_code == 0
    assert runner.invoke(app, ["hunt", "--no-run", "--file", "state.py"]).exit_code == 0

    explain_result = runner.invoke(app, ["explain", "--file", "state.py"])
    memory_result = runner.invoke(app, ["memory", "--type", "probe_generated"])
    explain_json_result = runner.invoke(app, ["explain", "--file", "state.py", "--json"])
    memory_json_result = runner.invoke(app, ["memory", "--type", "probe_generated", "--json"])

    assert explain_result.exit_code == 0, explain_result.output
    assert "mutable_default_argument" in explain_result.output
    assert "Mutable default arguments" in explain_result.output
    assert memory_result.exit_code == 0, memory_result.output
    assert "probe_generated" in memory_result.output
    assert "state.py" in memory_result.output
    assert json.loads(explain_json_result.output)[0]["risk"]["risk_type"] == "mutable_default_argument"
    assert json.loads(memory_json_result.output)[0]["event_type"] == "probe_generated"


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
    assert not (tmp_path / ".myco" / "reports" / "patches").exists()
    assert (tmp_path / ".myco" / "probes" / "generated_tests" / "test_myco_timezone_boundary_billing_py_aggressive.py").exists()
    assert (tmp_path / ".myco" / "probes" / "generated_tests" / "test_myco_timezone_boundary_billing_py_aggressive.md").exists()
    events = read_memory_events(tmp_path)
    assert any(event.event_type == "probe_failed" for event in events)

    patch_result = runner.invoke(app, ["patch", "--draft-diffs"])
    assert patch_result.exit_code == 0, patch_result.output
    assert "Application source files were not modified" in patch_result.output
    assert source_path.read_text(encoding="utf-8") == source_text
    assert list((tmp_path / ".myco" / "reports" / "patches").glob("*.patch"))


def test_cli_smoke_js_ts_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source_path = tmp_path / "billing.ts"
    source_text = (
        "export function invoiceDue() {\n"
        "  return new Date('2026-07-07')\n"
        "}\n"
    )
    source_path.write_text(source_text, encoding="utf-8")
    runner = CliRunner()

    init_result = runner.invoke(app, ["init"])
    scan_result = runner.invoke(app, ["scan"])
    ecosystems_result = runner.invoke(app, ["ecosystems", "--json"])
    risks_result = runner.invoke(app, ["risks"])
    verify_result = runner.invoke(app, ["verify", "--ecosystem", "javascript-typescript", "--no-run"])
    safe_result = runner.invoke(app, ["hunt", "--mode", "safe"])
    aggressive_result = runner.invoke(app, ["hunt", "--mode", "aggressive"])
    report_result = runner.invoke(app, ["report"])
    patch_result = runner.invoke(app, ["patch"])

    assert init_result.exit_code == 0, init_result.output
    assert scan_result.exit_code == 0, scan_result.output
    assert ecosystems_result.exit_code == 0, ecosystems_result.output
    assert risks_result.exit_code == 0, risks_result.output
    assert verify_result.exit_code == 0, verify_result.output
    assert safe_result.exit_code == 0, safe_result.output
    assert aggressive_result.exit_code == 0, aggressive_result.output
    assert report_result.exit_code == 0, report_result.output
    assert patch_result.exit_code == 0, patch_result.output
    assert "typescript" in risks_result.output
    ecosystems_payload = json.loads(ecosystems_result.output)
    assert ecosystems_payload[0]["verification_profiles"][0]["id"] == "js-ts-node-test"
    assert "dry_run" in verify_result.output
    assert source_path.read_text(encoding="utf-8") == source_text
    assert (tmp_path / ".myco" / "probes" / "generated_tests" / "test_myco_js_timezone_boundary_billing_ts.mjs").exists()
    assert (tmp_path / ".myco" / "probes" / "generated_tests" / "test_myco_js_timezone_boundary_billing_ts_aggressive.mjs").exists()
    assert (tmp_path / ".myco" / "probes" / "generated_tests" / "test_myco_js_timezone_boundary_billing_ts_aggressive.md").exists()
    assert build_console_report(tmp_path)["probes_generated"] == 2
    weather = (tmp_path / ".myco" / "reports" / "repo_weather.md").read_text(encoding="utf-8")
    assert "- JS/TS files: 1" in weather
    assert "- Language: typescript" in weather
