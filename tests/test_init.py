from mycopatch.core.paths import ensure_myco_layout


def test_init_creates_layout_and_is_idempotent(tmp_path):
    paths = ensure_myco_layout(tmp_path)
    paths_again = ensure_myco_layout(tmp_path)

    assert paths.myco.exists()
    assert paths.memory.exists()
    assert paths.spores.exists()
    assert paths.generated_tests.exists()
    assert paths.reports.exists()
    assert paths.config.exists()
    assert paths.constitution.exists()
    assert (paths.spores / "python-timezone-boundary.yaml").exists()
    assert paths_again.myco == paths.myco
