# Roadmap

## v0.1 Offline Python/Pytest MVP

- Initialize `.myco/`.
- Scan Python repositories.
- Detect timezone/date-boundary risks.
- Generate safe pytest probes.
- Run probes through a conservative command policy.
- Record append-only memory and cost events.
- Produce Markdown reports.

## v0.2 Stronger Probes

- Add AST-backed datetime evidence with line numbers.
- Add safe and aggressive probe modes.
- Add confidence scoring and `myco risks`.
- Improve test proximity detection.
- Add more built-in Python spores.

## v0.3 LLM Provider Adapters

- Add advisory provider interfaces without binding memory to one model.
- Keep offline heuristic mode as the default.
- Track token and dollar budgets for every provider call.
- Limit provider use to failure summaries, probe ideas, and patch recommendation text.

## v0.4 JS/TS Timezone Probes

- Scan `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, and `.cjs` files.
- Ignore declaration files, package caches, and common JS build outputs.
- Detect risky Date API usage with line-level evidence.
- Generate safe and aggressive `node:test` probes that read source as text.
- Keep package-manager commands out of the default safety policy.

## v0.5 More Spores And Explainability

- Add Python mutable default argument detection.
- Add Python broad exception swallowing detection.
- Add `myco explain` for human-readable risk explanations.
- Add `myco memory` for append-only memory inspection.
- Keep source patching recommendation-only.

## v0.6 Multi-Ecosystem Verification

- Detect Python, JS/TS, Go, Rust, Java/Kotlin, .NET, Ruby, and PHP ecosystems.
- Read common manifests and report framework hints.
- Add `myco ecosystems` for language, framework, and verification profile inventory.
- Add `myco verify` with dry-run as the default.
- Require `--allow-project-tests` or config opt-in before running project test commands.
- Keep dependency install, network access, and automatic patching blocked.

## v0.6.1 Safety And Release Hardening

- Close arbitrary Python command and file-symlink policy bypasses.
- Execute nested project profiles from their manifest directory.
- Return non-zero status for failed or blocked project verification.
- Recover valid memory around malformed JSONL records and diagnose corruption.
- Enforce hunt and external-provider budgets before work begins.
- Test Python 3.11 through 3.13 and build distributions in CI.

## v0.7 Guarded Patch Generation

- Generate minimal patches only from reproducible failures.
- Require patch diffs and rollback instructions.
- Add stronger policy checks before write operations.

## v0.8 Local Model Routing

- Support local models for low-risk summarization and probe drafting.
- Route tasks by cost, privacy, and confidence.
- Keep offline operation as the default path.

## v1.0 Spore Marketplace

- Share reusable spores.
- Sign and verify spores.
- Support project-level trust policies.
- Build community-maintained immune memory workflows.
