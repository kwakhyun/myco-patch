# MycoPatch

MycoPatch is an offline immune system for codebases.

Most coding agents wait for a user to describe a bug. MycoPatch scans a repository, predicts fragile areas, creates small probes, runs them safely, records evidence, and keeps reusable immune memory under `.myco/`.

Version 0.1 is intentionally modest: it is a safe Python + pytest MVP with deterministic heuristics and no LLM calls.

## Why It Is Different

- Pull requests are antibodies: patches should answer reproducible evidence.
- Tests are symptoms made visible: a probe should expose the risk before a fix is proposed.
- Spores are reusable bug-pattern capsules: risk knowledge is stored outside any one model.
- Immune memory survives model changes: findings and outcomes are append-only JSONL.
- Local-first by default: no APIs, no background service, no network dependency.

## Installation

For local development:

```bash
pip install -e ".[dev]"
```

Then verify the CLI:

```bash
myco --help
pytest
```

## Quickstart

From the root of a Python repository:

```bash
myco init
myco scan
myco hunt --budget 30000
myco report
myco patch
```

`myco hunt` uses deterministic offline heuristics. By default it generates a safe pytest probe and runs only that generated probe file.

## The `.myco/` Directory

```text
.myco/
  memory/
    repo_constitution.md
    failure_patterns.jsonl
    accepted_patches.jsonl
    rejected_patches.jsonl
    negative_results.jsonl
  spores/
    python-timezone-boundary.yaml
  probes/
    generated_tests/
  reports/
    repo_weather.md
    cost_ledger.jsonl
    immune_history.md
```

The directory is auditable and append-oriented. It is ignored by default in this repository's `.gitignore`; each downstream project can choose whether to commit its immune memory.

## Spores

A spore is a YAML capsule that describes a risk pattern, triggers, probe strategy, budget, and safety constraints.

The first built-in spore is `python-timezone-boundary`. It looks for patterns such as `datetime.now`, `datetime.utcnow`, `date.today`, naive datetime construction, and business names like billing, invoice, subscription, expiry, renewal, deadline, payment, and report.

## Safety Model

MycoPatch v0.1 blocks dangerous commands by default and allows only a narrow local command set:

- `python`
- `python3`
- `pytest`
- `git status`
- `git diff`

Generated probes do not import application code by default. They act as executable risk markers so the pipeline can be verified without hallucinating project-specific behavior.

## Current Limitations

- Python + pytest only.
- Timezone/date-boundary spore only.
- Probe generation is heuristic and conservative.
- Patch generation is recommendation-only.
- No LLM provider integrations yet.
- No autonomous source-code modification.

## Roadmap

- v0.1: offline Python/pytest MVP.
- v0.2: stronger probes and richer risk evidence.
- v0.3: LLM provider adapters behind auditable interfaces.
- v0.4: guarded patch generation from reproducible failures.
- v0.5: local model routing.
- v1.0: spore marketplace and shared immune memory workflows.

