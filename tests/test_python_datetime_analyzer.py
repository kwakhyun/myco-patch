from mycopatch.core.python_datetime_analyzer import analyze_datetime_risks


def test_ast_datetime_analyzer_detects_patterns_with_line_numbers():
    source = "\n".join(
        [
            "from datetime import date, datetime, timezone",
            "now = datetime.now()",
            "utc = datetime.utcnow()",
            "today = date.today()",
            "naive = datetime(2026, 1, 1)",
            "aware = datetime(2026, 1, 1, tzinfo=timezone.utc)",
            "labeled = naive.replace(tzinfo=timezone.utc)",
            "if now < datetime.utcnow():",
            "    pass",
        ]
    )

    evidence = analyze_datetime_risks(source)
    found = {(item.line_number, item.pattern) for item in evidence}

    assert (2, "datetime.now()") in found
    assert (3, "datetime.utcnow()") in found
    assert (4, "date.today()") in found
    assert (5, "datetime(...)") in found
    assert (7, "replace(tzinfo=...)") in found
    assert (8, "datetime.utcnow()") in found
    assert (8, "timezone-naive comparison") in found
    assert (6, "datetime(...)") not in found

