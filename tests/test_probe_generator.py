from mycopatch.core.paths import ensure_myco_layout
from mycopatch.core.probe_generator import generate_timezone_probe
from mycopatch.core.risk_mapper import map_timezone_risks
from mycopatch.core.repo_scanner import scan_repository
from mycopatch.core.spore_loader import load_spores


def test_probe_generator_creates_deterministic_safe_probe(tmp_path):
    ensure_myco_layout(tmp_path)
    (tmp_path / "billing.py").write_text(
        "from datetime import datetime\n"
        "def renew():\n"
        "    return datetime.utcnow()\n",
        encoding="utf-8",
    )
    risk = map_timezone_risks(scan_repository(tmp_path))[0]
    spore = next(item for item in load_spores(tmp_path) if item.name == "python-timezone-boundary")

    probe = generate_timezone_probe(tmp_path, risk, spore)
    probe_again = generate_timezone_probe(tmp_path, risk, spore)
    content = (tmp_path / probe.path).read_text(encoding="utf-8")
    conftest = tmp_path / ".myco" / "probes" / "generated_tests" / "conftest.py"

    assert probe.path == probe_again.path
    assert conftest.exists()
    assert "mycopatch_probe" in conftest.read_text(encoding="utf-8")
    assert "pytest.mark.mycopatch_probe" in content
    assert "datetime.utcnow" in content
    assert "does not import application" in content
    assert probe.safe_default


def test_probe_generator_creates_aggressive_probe_and_report(tmp_path):
    ensure_myco_layout(tmp_path)
    source_path = tmp_path / "billing.py"
    original_source = (
        "from datetime import datetime\n"
        "def renew():\n"
        "    return datetime.utcnow()\n"
    )
    source_path.write_text(original_source, encoding="utf-8")
    risk = map_timezone_risks(scan_repository(tmp_path))[0]
    spore = next(item for item in load_spores(tmp_path) if item.name == "python-timezone-boundary")

    probe = generate_timezone_probe(tmp_path, risk, spore, mode="aggressive")
    content = (tmp_path / probe.path).read_text(encoding="utf-8")
    report = tmp_path / (probe.explanation_path or "")

    assert probe.path.endswith("_aggressive.py")
    assert probe.mode == "aggressive"
    assert not probe.safe_default
    assert report.exists()
    assert report.parent == tmp_path / ".myco" / "probes" / "generated_tests"
    assert "AGGRESSIVE PROBE" in content
    assert "assert risky_pattern not in source" in content
    assert "Why This Probe May Fail" in report.read_text(encoding="utf-8")
    assert source_path.read_text(encoding="utf-8") == original_source
