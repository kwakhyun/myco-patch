from typer.testing import CliRunner

from mycopatch.cli import app


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
    assert (tmp_path / ".myco" / "reports" / "repo_weather.md").exists()
    assert list((tmp_path / ".myco" / "probes" / "generated_tests").glob("test_myco_timezone_boundary_*.py"))
    assert (tmp_path / ".myco" / "reports" / "patch_recommendations.md").exists()

