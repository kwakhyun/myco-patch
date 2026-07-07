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


def test_probe_generator_creates_js_ts_node_test_probes(tmp_path):
    ensure_myco_layout(tmp_path)
    source_path = tmp_path / "billing.ts"
    original_source = (
        "export function invoiceDue() {\n"
        "  return new Date('2026-07-07')\n"
        "}\n"
    )
    source_path.write_text(original_source, encoding="utf-8")
    risk = map_timezone_risks(scan_repository(tmp_path))[0]
    spore = next(item for item in load_spores(tmp_path) if item.name == "js-ts-timezone-boundary")

    safe_probe = generate_timezone_probe(tmp_path, risk, spore, mode="safe")
    aggressive_probe = generate_timezone_probe(tmp_path, risk, spore, mode="aggressive")
    safe_content = (tmp_path / safe_probe.path).read_text(encoding="utf-8")
    aggressive_content = (tmp_path / aggressive_probe.path).read_text(encoding="utf-8")

    assert safe_probe.path.endswith(".mjs")
    assert aggressive_probe.path.endswith("_aggressive.mjs")
    assert safe_probe.test_runner == "node-test"
    assert aggressive_probe.test_runner == "node-test"
    assert "node:test" in safe_content
    assert "node:assert/strict" in safe_content
    assert "source.includes(riskyPattern)" in safe_content
    assert "!source.includes(riskyPattern)" in aggressive_content
    assert (tmp_path / (aggressive_probe.explanation_path or "")).exists()
    assert source_path.read_text(encoding="utf-8") == original_source


def test_probe_generator_creates_python_bug_pattern_probe(tmp_path):
    ensure_myco_layout(tmp_path)
    source_path = tmp_path / "state.py"
    original_source = (
        "def add_item(item, items=[]):\n"
        "    items.append(item)\n"
        "    return items\n"
    )
    source_path.write_text(original_source, encoding="utf-8")
    risk = next(
        item
        for item in map_timezone_risks(scan_repository(tmp_path))
        if item.risk_type == "mutable_default_argument"
    )
    spore = next(item for item in load_spores(tmp_path) if item.name == "python-mutable-default-argument")

    probe = generate_timezone_probe(tmp_path, risk, spore)
    content = (tmp_path / probe.path).read_text(encoding="utf-8")

    assert probe.path == ".myco/probes/generated_tests/test_myco_python_mutable_default_argument_state_py.py"
    assert probe.risk_type == "mutable_default_argument"
    assert "mutable_default_argument" in content
    assert "def add_item(item, items=[]):" in content
    assert source_path.read_text(encoding="utf-8") == original_source
