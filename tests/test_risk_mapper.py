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


def test_risk_mapper_detects_js_ts_nearby_test_file(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "billing.ts").write_text(
        "export function deadline() {\n"
        "  return new Date('2026-07-07')\n"
        "}\n",
        encoding="utf-8",
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "billing.test.ts").write_text("test('deadline', () => {})\n", encoding="utf-8")

    risks = map_timezone_risks(scan_repository(tmp_path))

    assert risks[0].file_path == "src/billing.ts"
    assert risks[0].language == "typescript"
    assert risks[0].nearby_test_detected


def test_risk_mapper_emits_python_bug_pattern_risks(tmp_path):
    (tmp_path / "state.py").write_text(
        "def add_item(item, items=[]):\n"
        "    items.append(item)\n"
        "    return items\n"
        "\n"
        "def sync_payment():\n"
        "    try:\n"
        "        return int('x')\n"
        "    except Exception:\n"
        "        pass\n",
        encoding="utf-8",
    )

    risks = map_timezone_risks(scan_repository(tmp_path))
    risk_types = {risk.risk_type for risk in risks}

    assert "mutable_default_argument" in risk_types
    assert "broad_exception_swallow" in risk_types
    assert all(risk.language == "python" for risk in risks)


def test_timezone_keywords_do_not_create_timezone_risk_without_time_api(tmp_path):
    (tmp_path / "payment.py").write_text(
        "def sync_payment():\n"
        "    return 'ok'\n",
        encoding="utf-8",
    )

    risks = map_timezone_risks(scan_repository(tmp_path))

    assert risks == []
