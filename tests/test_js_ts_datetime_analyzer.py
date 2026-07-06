from mycopatch.core.js_ts_datetime_analyzer import analyze_js_ts_datetime_risks


def test_js_ts_datetime_analyzer_detects_patterns_with_line_numbers():
    source = "\n".join(
        [
            "const now = new Date()",
            "const ts = Date.now()",
            "const parsed = Date.parse(input)",
            'const deadline = new Date("2026-07-07")',
            "const day = now.getDate()",
            "now.setMonth(11)",
        ]
    )

    evidence = analyze_js_ts_datetime_risks(source)
    found = {(item.line_number, item.pattern) for item in evidence}

    assert (1, "new Date()") in found
    assert (2, "Date.now()") in found
    assert (3, "Date.parse(...)") in found
    assert (4, 'new Date("YYYY-MM-DD")') in found
    assert (5, "getDate()") in found
    assert (6, "setMonth()") in found

