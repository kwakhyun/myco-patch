from mycopatch.core.repo_scanner import scan_repository
from mycopatch.core.risk_mapper import map_timezone_risks


def test_risk_mapper_detects_nested_nearby_test_file(tmp_path):
    package = tmp_path / "package"
    package.mkdir()
    (package / "module.py").write_text(
        "from datetime import datetime\n"
        "def expires_at():\n"
        "    return datetime.utcnow()\n",
        encoding="utf-8",
    )
    test_package = tmp_path / "tests" / "package"
    test_package.mkdir(parents=True)
    (test_package / "test_module.py").write_text("def test_expires_at():\n    assert True\n", encoding="utf-8")

    risks = map_timezone_risks(scan_repository(tmp_path))

    assert risks[0].file_path == "package/module.py"
    assert risks[0].nearby_test_detected
    assert "nearby test file detected" in risks[0].reason
