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


def test_scanner_detects_replace_tzinfo_and_naive_comparison(tmp_path):
    (tmp_path / "reports.py").write_text(
        "from datetime import datetime, timezone\n"
        "deadline = datetime(2026, 1, 1)\n"
        "current = datetime.now()\n"
        "normalized = deadline.replace(tzinfo=timezone.utc)\n"
        "expired = current > deadline\n",
        encoding="utf-8",
    )

    result = scan_repository(tmp_path)
    finding = result.python_files[0]

    assert finding.uses_naive_datetime_construction
    assert finding.uses_datetime_now
    assert finding.uses_replace_tzinfo
    assert finding.uses_timezone_naive_comparison
    assert any(item.line_number == 5 and item.pattern == "timezone-naive comparison" for item in finding.datetime_evidence)


def test_scanner_detects_js_ts_files_and_ignores_build_outputs(tmp_path):
    (tmp_path / "billing.ts").write_text(
        "export const due = new Date('2026-07-07')\n"
        "export const renewed = Date.now()\n"
        "export const month = due.getMonth()\n",
        encoding="utf-8",
    )
    (tmp_path / "types.d.ts").write_text("declare const x: Date\n", encoding="utf-8")
    next_dir = tmp_path / ".next"
    next_dir.mkdir()
    (next_dir / "ignored.js").write_text("const x = Date.now()\n", encoding="utf-8")
    coverage_dir = tmp_path / "coverage"
    coverage_dir.mkdir()
    (coverage_dir / "ignored.ts").write_text("const x = Date.now()\n", encoding="utf-8")

    result = scan_repository(tmp_path)

    assert result.python_file_count == 0
    assert result.js_ts_file_count == 1
    finding = result.js_ts_files[0]
    assert finding.path == "billing.ts"
    assert finding.language == "typescript"
    assert finding.uses_js_new_date
    assert finding.uses_js_date_string_constructor
    assert finding.uses_js_date_now
    assert finding.uses_js_local_date_accessors
