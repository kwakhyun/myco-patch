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

## v0.4 Patch Generation

- Generate minimal patches only from reproducible failures.
- Require patch diffs and rollback instructions.
- Add stronger policy checks before write operations.

## v0.5 Local Model Routing

- Support local models for low-risk summarization and probe drafting.
- Route tasks by cost, privacy, and confidence.
- Keep offline operation as the default path.

## v1.0 Spore Marketplace

- Share reusable spores.
- Sign and verify spores.
- Support project-level trust policies.
- Build community-maintained immune memory workflows.
