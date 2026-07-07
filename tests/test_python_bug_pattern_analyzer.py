from mycopatch.core.python_bug_pattern_analyzer import analyze_python_bug_patterns


def test_python_bug_pattern_analyzer_detects_mutable_defaults_and_swallowed_exceptions():
    source = "\n".join(
        [
            "def add_item(item, items=[]):",
            "    items.append(item)",
            "    return items",
            "",
            "def load_payment():",
            "    try:",
            "        return int('x')",
            "    except Exception:",
            "        pass",
            "",
            "def ignored():",
            "    try:",
            "        return int('x')",
            "    except ValueError:",
            "        return None",
        ]
    )

    evidence = analyze_python_bug_patterns(source)
    found = {(item.line_number, item.pattern) for item in evidence}

    assert (1, "mutable default argument") in found
    assert (8, "broad exception swallowing") in found
    assert not any(item.line_number == 13 for item in evidence)
