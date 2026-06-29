from mycopatch.core.repo_scanner import scan_repository


def test_scanner_ignores_expected_directories(tmp_path):
    (tmp_path / ".myco").mkdir()
    (tmp_path / ".myco" / "ignored.py").write_text("from datetime import datetime\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.py").write_text("from datetime import datetime\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")

    result = scan_repository(tmp_path)

    assert [finding.path for finding in result.python_files] == ["app.py"]


def test_scanner_detects_datetime_patterns_and_tests(tmp_path):
    (tmp_path / "billing.py").write_text(
        "from datetime import date, datetime\n"
        "def due():\n"
        "    invoice_deadline = date.today()\n"
        "    return datetime.utcnow()\n",
        encoding="utf-8",
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_billing.py").write_text("def test_due():\n    assert True\n", encoding="utf-8")

    result = scan_repository(tmp_path)
    billing = next(finding for finding in result.python_files if finding.path == "billing.py")
    test_file = next(finding for finding in result.python_files if finding.path == "tests/test_billing.py")

    assert billing.imports_datetime
    assert billing.uses_datetime_utcnow
    assert billing.uses_date_today
    assert billing.contains_timezone_keywords
    assert not billing.is_test_file
    assert test_file.is_test_file

