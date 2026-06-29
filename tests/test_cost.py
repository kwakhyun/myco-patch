import json

from mycopatch.core.cost import estimate_tokens, record_cost_event
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

