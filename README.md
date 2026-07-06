# MycoPatch

[한국어](README.ko.md) | English

MycoPatch is an offline immune system for codebases.

Most coding agents wait for a user to describe a bug. MycoPatch scans a repository, predicts fragile areas, creates small probes, runs them safely, records evidence, and keeps reusable immune memory under `.myco/`.

Version 0.4 is intentionally scoped: it is a safe Python + pytest and JavaScript/TypeScript + `node:test` timezone/date-boundary bug-hunting tool with deterministic heuristics. Optional model-provider interfaces exist for advisory text, but offline heuristic mode is the default.

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

From the root of a Python or JavaScript/TypeScript repository:

```bash
myco init
myco init  # safe to run again; verifies the existing .myco layout
myco scan
myco risks
myco hunt --budget 30000 --mode safe
myco doctor
myco report
myco patch
```

What to expect:

- `myco init` creates `.myco/`, installs the built-in timezone spores, and is idempotent.
- `myco scan` writes `.myco/reports/repo_weather.md` with detected Python files, JS/TS files, tests, top risks, and offline cost accounting.
- `myco risks` prints the top findings with score, confidence, nearby-test status, and first evidence line.
- `myco hunt --budget 30000 --mode safe` uses deterministic offline heuristics. It generates a safe pytest or `node:test` risk-marker probe and runs only that generated probe file.
- `myco hunt --budget 30000 --mode aggressive` may generate a failing probe when static evidence is clear. Aggressive probes are labeled, write an explanation markdown file beside the generated test, and still never modify application source files.
- `myco hunt --dry-run`, `--language`, `--file`, `--limit`, and `--all` let you preview or target probe generation without changing application source files.
- `myco scan --json` and `myco risks --json` produce machine-readable output for scripts and CI.
- `myco doctor` checks initialization, pytest/node availability, spore counts, config validity, and provider network status.
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
    js-ts-timezone-boundary.yaml
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

The built-in spores are:

- `python-timezone-boundary`, which looks for patterns such as `datetime.now`, `datetime.utcnow`, `date.today`, naive datetime construction, timezone-naive comparisons, and business names like billing, invoice, subscription, expiry, renewal, deadline, payment, and report.
- `js-ts-timezone-boundary`, which scans `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, and `.cjs` files for patterns such as `new Date()`, `Date.now()`, `Date.parse(...)`, `new Date("YYYY-MM-DD")`, local date getters/setters, and the same timezone-sensitive business names.

JS/TS probes are dependency-free by default. They use Node's built-in `node:test` runner, read target source files as text, and never import application code or run package-manager commands.

## Safety Model

MycoPatch blocks dangerous commands by default and allows only a narrow local command set:

- `python`
- `python3`
- `pytest`
- `node --test .myco/probes/generated_tests/*.mjs`
- `git status`
- `git diff`

Package-manager commands such as `npm`, `npx`, `yarn`, and `pnpm` are not allowed in v0.4. Generated probes do not import application code by default. They act as executable risk markers so the pipeline can be verified without hallucinating project-specific behavior.

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

- Timezone/date-boundary spores only.
- JS/TS support is static and dependency-free; it does not parse full TypeScript semantics, transpile files, or integrate with Jest/Vitest yet.
- Probe generation is heuristic. Safe mode is conservative; aggressive mode still uses static evidence only.
- Patch generation is recommendation-only.
- Model providers are advisory only; no source patching uses model output.
- No autonomous source-code modification.

## Roadmap

- v0.1: offline Python/pytest MVP.
- v0.2: safe/aggressive probe modes, AST-backed datetime evidence, confidence scoring, and risk tables.
- v0.3: optional advisory model-provider interfaces with offline-first cost tracking.
- v0.4: dependency-free JS/TS timezone probes using Node's built-in test runner.
- v0.5: guarded patch generation from reproducible failures.
- v0.6: local model routing.
- v1.0: spore marketplace and shared immune memory workflows.
