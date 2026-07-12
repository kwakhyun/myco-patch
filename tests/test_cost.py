import json

from mycopatch.core.cost import estimate_tokens, read_cost_events, record_cost_event
from mycopatch.core.jsonl import audit_repo_jsonl
from mycopatch.core.memory import append_memory_event, read_memory_events
from mycopatch.core.paths import ensure_myco_layout


def test_cost_records_jsonl_event(tmp_path):
    paths = ensure_myco_layout(tmp_path)
    event = record_cost_event(
        tmp_path,
        input_text="abcd" * 10,
        output_text="hello",
        budget_limit=30000,
        notes="unit test",
    )

    lines = paths.cost_ledger.read_text(encoding="utf-8").splitlines()
    payload = json.loads(lines[-1])

    assert event.estimated_cost_usd == 0
    assert payload["model_name"] == "offline-heuristic"
    assert payload["budget_limit"] == 30000
    assert estimate_tokens("abcd") == 1


def test_cost_reader_skips_invalid_jsonl_line_and_reports_it(tmp_path):
    paths = ensure_myco_layout(tmp_path)
    record_cost_event(tmp_path, input_text="valid")
    with paths.cost_ledger.open("a", encoding="utf-8") as handle:
        handle.write("not-json\n")

    assert len(read_cost_events(tmp_path)) == 1
    issues = audit_repo_jsonl(tmp_path)
    assert len(issues) == 1
    assert issues[0].path == paths.cost_ledger
    assert issues[0].line_number == 2


def test_memory_reader_keeps_valid_events_around_invalid_line(tmp_path):
    paths = ensure_myco_layout(tmp_path)
    append_memory_event(tmp_path, "scan_completed", {"count": 1})
    with (paths.memory / "failure_patterns.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("{broken\n")
    append_memory_event(tmp_path, "probe_generated", {"path": "probe.py"})

    events = read_memory_events(tmp_path)

    assert [event.event_type for event in events] == ["scan_completed", "probe_generated"]
    assert audit_repo_jsonl(tmp_path)[0].line_number == 2
