# MycoPatch

English | [한국어](README.md)

MycoPatch is an offline immune system for codebases.

## Core Value

MycoPatch's core value is simple: **create reproducible evidence before trusting an AI-generated code change**.

Most coding agents jump from a user-described bug to a patch. MycoPatch takes the opposite path. It scans the repository, identifies fragile areas, creates small probes/tests, runs them safely, records evidence and cost, and only then suggests a repair direction.

Use this CLI when you want to:

- find risky code before a user reports a bug
- reduce plausible but unsupported AI patches
- leave small tests and reports behind as evidence
- build `.myco/` immune memory that survives model changes
- stay local-first without external APIs, network calls, or dangerous commands
- detect Python/JavaScript/TypeScript recurring bug patterns and safely inspect verification paths for popular ecosystems such as Go, Rust, Java, .NET, Ruby, and PHP

In one sentence, MycoPatch CLI is **not an automatic patch generator**. It is a safe bug-hunting tool that finds weak spots in a codebase and leaves auditable evidence behind.

Most coding agents wait for a user to describe a bug. MycoPatch scans a repository, predicts fragile areas, creates small probes, runs them safely, records evidence, and keeps reusable immune memory under `.myco/`.

Version 0.7 remains deliberately safety-scoped. It can draft a guarded unified diff and rollback document for a narrow known pattern only when explicitly requested. MycoPatch still does not apply patches to application source files.

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
myco ecosystems
myco risks
myco explain
myco hunt --budget 30000 --mode safe
myco verify --no-run
myco doctor
myco report
myco memory
myco patch
myco patch --draft-diffs
myco --version
```

What to expect:

- `myco init` creates `.myco/`, installs the built-in spores, and is idempotent.
- `myco scan` writes `.myco/reports/repo_weather.md` with detected Python files, JS/TS files, ecosystems, tests, top risks, and offline cost accounting.
- `myco ecosystems` shows detected Python, JS/TS, Go, Rust, Java/Kotlin, .NET, Ruby, and PHP manifests, framework hints, and verification profile candidates.
- `myco risks` prints the top findings with score, confidence, nearby-test status, and first evidence line.
- `myco explain` explains why detected risks matter and lists human review steps.
- `myco hunt --budget 30000 --mode safe` uses deterministic offline heuristics. The budget is a hard estimated-token limit; an insufficient budget records an inconclusive event without generating a probe.
- `myco hunt --budget 30000 --mode aggressive` may generate a failing probe when static evidence is clear. Aggressive probes are labeled, write an explanation markdown file beside the generated test, and still never modify application source files.
- `myco hunt --dry-run`, `--language`, `--file`, `--limit`, and `--all` let you preview or target probe generation without changing application source files.
- `myco scan --json` and `myco risks --json` produce machine-readable output for scripts and CI.
- `myco verify --no-run` previews project verification profiles without executing them.
- `myco verify --run --allow-project-tests` executes recognized profiles from their manifest directory. Test failures and policy blocks return exit code 1.
- `myco doctor` also reports malformed JSONL records with file and line locations.
- `myco report` summarizes memory events, probe outcomes, and the zero-dollar offline cost ledger.
- `myco memory` shows append-only events from `.myco/memory/*.jsonl`.
- `myco patch` does not automatically edit arbitrary source files. It writes recommendations only when reproducible probe failures have been recorded.
- `myco patch --draft-diffs` writes eligible unified diff and rollback artifacts under `.myco/reports/patches/`. The built-in v0.7 transformation is limited to Python `datetime.utcnow()` and is never applied automatically.

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
    python-mutable-default-argument.yaml
    python-broad-exception-swallow.yaml
  probes/
    generated_tests/
  reports/
    repo_weather.md
    cost_ledger.jsonl
    immune_history.md
    guarded_patch_drafts.md
    patches/
  config.toml
```

The directory is auditable and append-oriented. It is ignored by default in this repository's `.gitignore`; each downstream project can choose whether to commit its immune memory.

## Spores

A spore is a YAML capsule that describes a risk pattern, triggers, probe strategy, budget, and safety constraints.

The built-in spores are:

- `python-timezone-boundary`, which looks for patterns such as `datetime.now`, `datetime.utcnow`, `date.today`, naive datetime construction, timezone-naive comparisons, and business names like billing, invoice, subscription, expiry, renewal, deadline, payment, and report.
- `js-ts-timezone-boundary`, which scans `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, and `.cjs` files for patterns such as `new Date()`, `Date.now()`, `Date.parse(...)`, `new Date("YYYY-MM-DD")`, local date getters/setters, and the same timezone-sensitive business names.
- `python-mutable-default-argument`, which finds mutable default arguments such as `def f(items=[])` that can share state across calls.
- `python-broad-exception-swallow`, which finds broad exception handlers such as `except Exception: pass` that can hide failure evidence.

JS/TS probes are dependency-free by default. They use Node's built-in `node:test` runner, read target source files as text, and never import application code or run package-manager commands.

## Safety Model

MycoPatch blocks dangerous commands by default and allows only a narrow local command set:

- `python --version` or `python3 --version`
- generated-probe `pytest .myco/probes/generated_tests/*.py`
- `node --test .myco/probes/generated_tests/*.mjs`
- `git status`
- `git diff`

In v0.6.1, `myco verify` does not run project-wide tests by default. When enabled, it applies proxy blocking and ecosystem-specific offline settings. This discourages package downloads but is not an OS sandbox that can prevent explicitly allowed test code from opening raw sockets.

Dependency installation and network-prone commands such as `npm`, `npx`, `yarn`, `pnpm`, `pip install`, `go get`, `cargo install`, `bundle install`, `composer install`, and `dotnet restore` remain blocked. Generated probes do not import application code by default. They act as executable risk markers so the pipeline can be verified without hallucinating project-specific behavior.

Aggressive probes are opt-in. They may intentionally fail while a risky static pattern remains, but they are written only under `.myco/probes/generated_tests/` and include a markdown explanation for human review.

## Optional Model Providers

MycoPatch is offline-first. `.myco/config.toml` defaults to:

```toml
default_provider = "offline"
model_name = "offline-heuristic"
allow_network_for_model_provider = false
allow_project_test_commands = false
```

Provider interfaces are limited to advisory tasks:

- summarizing failure logs
- suggesting probe ideas
- drafting patch recommendation text

They are not used to generate source-code diffs or apply patches. Guarded diffs use deterministic local transformations only. External providers require both `allow_network_for_model_provider = true` and a positive `max_cost_usd`.

## Current Limitations

- Supported spores are still limited to small deterministic patterns.
- Multi-ecosystem support means detection plus safe verification profiles. Deep bug-pattern analysis is not implemented for every language yet.
- JS/TS support is static and dependency-free; it does not parse full TypeScript semantics, transpile files, or integrate with Jest/Vitest yet.
- Probe generation is heuristic. Safe mode is conservative; aggressive mode still uses static evidence only.
- Guarded patch generation is opt-in artifact drafting. It does not apply source changes and currently supports only Python `datetime.utcnow()`.
- Model providers are advisory only; no source patching uses model output.
- No autonomous source-code modification.

## Roadmap

- v0.1: offline Python/pytest MVP.
- v0.2: safe/aggressive probe modes, AST-backed datetime evidence, confidence scoring, and risk tables.
- v0.3: optional advisory model-provider interfaces with offline-first cost tracking.
- v0.4: dependency-free JS/TS timezone probes using Node's built-in test runner.
- v0.5: Python mutable defaults, broad exception swallowing, `myco explain`, and `myco memory`.
- v0.6: ecosystem detection and explicit-allow project verification profiles for Python, JS/TS, Go, Rust, Java/Kotlin, .NET, Ruby, and PHP.
- v0.6.1: command-policy, repository-boundary, monorepo working-directory, JSONL recovery, budget, exit-code, and release-CI hardening.
- v0.7: opt-in guarded diff and rollback artifacts for known-pattern failures, without source application.
- v0.8: local model routing.
- v1.0: spore marketplace and shared immune memory workflows.
