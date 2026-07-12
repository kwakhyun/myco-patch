from mycopatch.core.memory import append_memory_event, read_memory_events
from mycopatch.core.patch_drafter import create_guarded_patch_drafts
from mycopatch.core.paths import ensure_myco_layout
from mycopatch.core.reporter import build_console_report


def _record_utcnow_failure(repo_root, target_file="billing.py"):
    append_memory_event(
        repo_root,
        "probe_failed",
        {
            "probe": {
                "id": "timezone_boundary_billing_py_aggressive",
                "target_file": target_file,
                "risk_type": "timezone_boundary",
                "path": ".myco/probes/generated_tests/test_probe.py",
                "mode": "aggressive",
                "evidence": ["L5: return datetime.utcnow()"],
            },
            "result": {"status": "failed", "return_code": 1},
        },
    )


def test_guarded_patch_draft_is_deterministic_and_does_not_modify_source(tmp_path):
    paths = ensure_myco_layout(tmp_path)
    source_path = tmp_path / "billing.py"
    source = (
        "from datetime import datetime\n"
        "\n"
        "def expires():\n"
        "    return datetime.utcnow()\n"
    )
    source_path.write_text(source, encoding="utf-8")
    _record_utcnow_failure(tmp_path)

    first, first_rejected = create_guarded_patch_drafts(tmp_path)
    first_patch = (tmp_path / first[0].patch_path).read_text(encoding="utf-8")
    second, second_rejected = create_guarded_patch_drafts(tmp_path)
    second_patch = (tmp_path / second[0].patch_path).read_text(encoding="utf-8")

    assert first_rejected == second_rejected == []
    assert source_path.read_text(encoding="utf-8") == source
    assert first[0].patch_path == second[0].patch_path
    assert first_patch == second_patch
    assert "from datetime import datetime, timezone" in first_patch
    assert "datetime.now(timezone.utc)" in first_patch
    assert str(tmp_path) not in first_patch
    assert (tmp_path / first[0].rollback_path).exists()
    assert paths.guarded_patch_report.exists()
    assert not first[0].applies_source_changes
    report = build_console_report(tmp_path)
    assert report["patch_drafts_created"] == 2
    assert report["patch_drafts_ineligible"] == 0


def test_guarded_patch_draft_rejects_unsupported_and_unsafe_targets(tmp_path):
    ensure_myco_layout(tmp_path)
    outside = tmp_path.parent / "outside.py"
    outside.write_text("from datetime import datetime\nvalue = datetime.utcnow()\n", encoding="utf-8")
    (tmp_path / "billing.py").symlink_to(outside)
    _record_utcnow_failure(tmp_path)

    drafts, rejected = create_guarded_patch_drafts(tmp_path)

    assert drafts == []
    assert "symlinks are not eligible" in rejected[0]
    assert any(event.event_type == "patch_draft_ineligible" for event in read_memory_events(tmp_path))


def test_guarded_patch_draft_does_not_replace_strings_or_comments(tmp_path):
    ensure_myco_layout(tmp_path)
    source_path = tmp_path / "billing.py"
    source = (
        "from datetime import datetime\n"
        "label = 'datetime.utcnow()'\n"
        "# datetime.utcnow()\n"
        "value = datetime.utcnow()\n"
    )
    source_path.write_text(source, encoding="utf-8")
    _record_utcnow_failure(tmp_path)

    drafts, _ = create_guarded_patch_drafts(tmp_path)
    patch_text = (tmp_path / drafts[0].patch_path).read_text(encoding="utf-8")

    assert "-label = 'datetime.utcnow()'" not in patch_text
    assert "+label = 'datetime.now(timezone.utc)'" not in patch_text
    assert "-# datetime.utcnow()" not in patch_text
    assert "-value = datetime.utcnow()" in patch_text


def test_guarded_patch_draft_reuses_existing_timezone_import(tmp_path):
    ensure_myco_layout(tmp_path)
    source_path = tmp_path / "billing.py"
    source_path.write_text(
        "from datetime import datetime, timezone\nvalue = datetime.utcnow()\n",
        encoding="utf-8",
    )
    _record_utcnow_failure(tmp_path)

    drafts, rejected = create_guarded_patch_drafts(tmp_path)
    patch_text = (tmp_path / drafts[0].patch_path).read_text(encoding="utf-8")

    assert rejected == []
    assert "-from datetime import datetime, timezone" not in patch_text
    assert "+from datetime import datetime, timezone" not in patch_text
    assert "+value = datetime.now(timezone.utc)" in patch_text
