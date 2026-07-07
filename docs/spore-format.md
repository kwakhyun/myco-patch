# Spore Format

A spore is a YAML file that describes a reusable risk pattern and a safe probe strategy.

## Schema

```yaml
name: python-timezone-boundary
version: 0.6.0
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

JavaScript/TypeScript spores use the same shape. The built-in JS/TS spore uses `probe.type: node-test` and is intentionally dependency-free:

```yaml
name: js-ts-timezone-boundary
version: 0.6.0
language: javascript-typescript
description: Detects Date API and date-boundary risks in JavaScript and TypeScript projects.
risk_type: timezone_boundary
triggers:
  path_keywords:
    - billing
    - invoice
    - subscription
    - schedule
    - expiry
    - deadline
    - renewal
    - payment
    - report
  code_patterns:
    - new Date()
    - Date.now()
    - Date.parse(...)
    - new Date("YYYY-MM-DD")
    - getDate()
    - setDate()
probe:
  type: node-test
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

Python bug-pattern spores also use the same shape. For example:

```yaml
name: python-mutable-default-argument
version: 0.6.0
language: python
description: Detects mutable default arguments that can leak state across calls.
risk_type: mutable_default_argument
triggers:
  path_keywords:
    - cache
    - state
  code_patterns:
    - "=[]"
    - "={}"
    - "=set()"
probe:
  type: pytest
  strategy: static_marker
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

For v0.6, new spores should be conservative:

- Prefer evidence that can be found by deterministic scanning.
- Generate probes that do not import application code unless the target contract is obvious.
- For JS/TS, prefer `node:test` probes that read source as text instead of running package-manager test commands.
- Keep write paths under `.myco/`.
- Set finite runtime and token budgets.
- Record enough description for a maintainer to audit the probe.

## Ecosystem Verification Is Separate

`myco ecosystems` and `myco verify` use manifest detection and verification profiles, not spore probe generation. A future spore may target Go, Rust, Java, .NET, Ruby, or PHP bug patterns, but v0.6 only inventories those ecosystems and safely dry-runs or explicitly runs recognized test profiles.
