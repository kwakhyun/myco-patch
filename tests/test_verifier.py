from mycopatch.core.models import Probe
from mycopatch.core.verifier import verify_probe
from mycopatch.core.paths import ensure_myco_layout


def test_verifier_dispatches_node_test_for_js_ts_probe(tmp_path, monkeypatch):
    ensure_myco_layout(tmp_path)
    probe_path = tmp_path / ".myco" / "probes" / "generated_tests" / "test_myco_js_timezone_boundary_billing_ts.mjs"
    probe_path.write_text("import test from 'node:test'\n", encoding="utf-8")
    probe = Probe(
        id="js_timezone_boundary_billing_ts",
        risk_type="timezone_boundary",
        target_file="billing.ts",
        path=".myco/probes/generated_tests/test_myco_js_timezone_boundary_billing_ts.mjs",
        evidence=[],
        spore_name="js-ts-timezone-boundary",
        test_runner="node-test",
    )
    calls = []

    def fake_which(command):
        return "/usr/bin/node" if command == "node" else None

    def fake_run_command(command, cwd, timeout_seconds):
        calls.append(command)
        from mycopatch.core.models import CommandResult

        return CommandResult(command=command, allowed=True, return_code=0, stdout="ok", stderr="")

    monkeypatch.setattr("mycopatch.core.verifier.shutil.which", fake_which)
    monkeypatch.setattr("mycopatch.core.verifier.run_command", fake_run_command)

    result = verify_probe(tmp_path, probe)

    assert result.status == "passed"
    assert calls == [["node", "--test", probe.path]]


def test_verifier_skips_node_test_when_node_missing(tmp_path, monkeypatch):
    ensure_myco_layout(tmp_path)
    probe_path = tmp_path / ".myco" / "probes" / "generated_tests" / "test_myco_js_timezone_boundary_billing_ts.mjs"
    probe_path.write_text("import test from 'node:test'\n", encoding="utf-8")
    probe = Probe(
        id="js_timezone_boundary_billing_ts",
        risk_type="timezone_boundary",
        target_file="billing.ts",
        path=".myco/probes/generated_tests/test_myco_js_timezone_boundary_billing_ts.mjs",
        evidence=[],
        spore_name="js-ts-timezone-boundary",
        test_runner="node-test",
    )

    monkeypatch.setattr("mycopatch.core.verifier.shutil.which", lambda command: None)

    result = verify_probe(tmp_path, probe)

    assert result.status == "skipped"
    assert "node is not available" in result.evidence[0]
