# MycoPatch

MycoPatch is an offline immune system for codebases.

Most coding agents wait for a user to describe a bug. MycoPatch scans a repository, predicts fragile areas, creates small probes, runs them safely, records evidence, and keeps reusable immune memory under `.myco/`.

Version 0.3 is intentionally modest: it is a safe Python + pytest bug-hunting tool with deterministic heuristics. Optional model-provider interfaces exist for advisory text, but offline heuristic mode is the default.

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
myco init  # safe to run again; verifies the existing .myco layout
myco scan
myco risks
myco hunt --budget 30000 --mode safe
myco report
myco patch
```

What to expect:

- `myco init` creates `.myco/`, installs the built-in timezone spore, and is idempotent.
- `myco scan` writes `.myco/reports/repo_weather.md` with detected Python files, tests, top risks, and offline cost accounting.
- `myco risks` prints the top findings with score, confidence, nearby-test status, and first evidence line.
- `myco hunt --budget 30000 --mode safe` uses deterministic offline heuristics. It generates a safe pytest risk-marker probe and runs only that generated probe file.
- `myco hunt --budget 30000 --mode aggressive` may generate a failing probe when static evidence is clear. Aggressive probes are labeled, write an explanation markdown file beside the generated test, and still never modify application source files.
- `myco report` summarizes memory events, probe outcomes, and the zero-dollar offline cost ledger.
- `myco patch` does not automatically edit arbitrary source files. It writes recommendations only when reproducible probe failures have been recorded.

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
  config.toml
```

The directory is auditable and append-oriented. It is ignored by default in this repository's `.gitignore`; each downstream project can choose whether to commit its immune memory.

## Spores

A spore is a YAML capsule that describes a risk pattern, triggers, probe strategy, budget, and safety constraints.

The first built-in spore is `python-timezone-boundary`. It looks for patterns such as `datetime.now`, `datetime.utcnow`, `date.today`, naive datetime construction, and business names like billing, invoice, subscription, expiry, renewal, deadline, payment, and report.

## Safety Model

MycoPatch blocks dangerous commands by default and allows only a narrow local command set:

- `python`
- `python3`
- `pytest`
- `git status`
- `git diff`

Generated probes do not import application code by default. They act as executable risk markers so the pipeline can be verified without hallucinating project-specific behavior.

Aggressive probes are opt-in. They may intentionally fail while a risky static pattern remains, but they are written only under `.myco/probes/generated_tests/` and include a markdown explanation for human review.

## Optional Model Providers

MycoPatch is offline-first. `.myco/config.toml` defaults to:

```toml
default_provider = "offline"
model_name = "offline-heuristic"
allow_network_for_model_provider = false
```

Provider interfaces are limited to advisory tasks:

- summarizing failure logs
- suggesting probe ideas
- drafting patch recommendation text

They are not used for direct source-code patching. External providers such as `openai-compatible` and `local-http` are never called unless `allow_network_for_model_provider = true` is explicitly set. Every provider call, including offline heuristic calls, is recorded in `.myco/reports/cost_ledger.jsonl`.

## Current Limitations

- Python + pytest only.
- Timezone/date-boundary spore only.
- Probe generation is heuristic. Safe mode is conservative; aggressive mode still uses static evidence only.
- Patch generation is recommendation-only.
- Model providers are advisory only; no source patching uses model output.
- No autonomous source-code modification.

## Roadmap

- v0.1: offline Python/pytest MVP.
- v0.2: safe/aggressive probe modes, AST-backed datetime evidence, confidence scoring, and risk tables.
- v0.3: optional advisory model-provider interfaces with offline-first cost tracking.
- v0.4: guarded patch generation from reproducible failures.
- v0.5: local model routing.
- v1.0: spore marketplace and shared immune memory workflows.
