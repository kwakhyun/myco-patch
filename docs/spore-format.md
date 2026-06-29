# Spore Format

A spore is a YAML file that describes a reusable risk pattern and a safe probe strategy.

## Schema

```yaml
name: python-timezone-boundary
version: 0.1.0
language: python
description: Detects naive datetime and date-boundary risks in Python projects.
risk_type: timezone_boundary
triggers:
  path_keywords:
    - billing
  code_patterns:
    - datetime.utcnow
probe:
  type: pytest
  strategy: boundary_dates
budget:
  max_input_tokens: 6000
  max_output_tokens: 1200
  max_runtime_seconds: 60
safety:
  network: deny
  write_paths:
    - .myco/probes/generated_tests
    - .myco/reports
    - .myco/memory
```

## Loading Rules

MycoPatch loads built-in spores first, then loads repo-local spores from `.myco/spores/`.

If a repo-local spore has the same `name` as a built-in spore, the local spore overrides the built-in one.

## Writing a New Spore

For v0.1, new spores should be conservative:

- Prefer evidence that can be found by deterministic scanning.
- Generate probes that do not import application code unless the target contract is obvious.
- Keep write paths under `.myco/`.
- Set finite runtime and token budgets.
- Record enough description for a maintainer to audit the probe.

