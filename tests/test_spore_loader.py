from mycopatch.core.paths import ensure_myco_layout
from mycopatch.core.spore_loader import load_builtin_spores, load_spores


def test_loads_builtin_spore():
    spores = load_builtin_spores()

    assert any(spore.name == "python-timezone-boundary" for spore in spores)
    assert any(spore.name == "js-ts-timezone-boundary" for spore in spores)
    assert any(spore.name == "python-mutable-default-argument" for spore in spores)
    assert any(spore.name == "python-broad-exception-swallow" for spore in spores)


def test_repo_local_spore_overrides_builtin(tmp_path):
    paths = ensure_myco_layout(tmp_path)
    local_spore = paths.spores / "python-timezone-boundary.yaml"
    local_spore.write_text(
        """
name: python-timezone-boundary
version: 9.9.9
language: python
description: Local override.
risk_type: timezone_boundary
triggers:
  path_keywords: [billing]
  code_patterns: [datetime.utcnow]
probe:
  type: pytest
  strategy: boundary_dates
budget:
  max_input_tokens: 1
  max_output_tokens: 1
  max_runtime_seconds: 1
safety:
  network: deny
  write_paths: [.myco/probes/generated_tests]
""",
        encoding="utf-8",
    )

    spores = load_spores(tmp_path)
    spore = next(item for item in spores if item.name == "python-timezone-boundary")

    assert spore.version == "9.9.9"
    assert spore.source == "local"
