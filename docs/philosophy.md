# Philosophy

MycoPatch treats a codebase as a living system with memory.

Normal coding agents usually begin after a user names a bug. MycoPatch begins earlier: it scans for fragile areas, creates small probes, verifies them locally, and records what it learned. The goal is not to make bigger guesses. The goal is to make smaller, auditable claims.

## Codebase Immune System

Pull requests are antibodies. They should respond to observed symptoms, not vague suspicion.

Tests are symptoms made visible. A good probe turns a fragile assumption into something executable.

Spores are reusable bug-pattern capsules. They keep risk knowledge portable across projects and model versions.

## Probe-First Development

MycoPatch v0.1 does not try to write arbitrary fixes. It first proves that the scan, probe, verification, memory, and report loop can run safely.

The initial generated tests are conservative executable markers. They identify risky code and give maintainers a stable place to build real regression coverage once the business rule is known.

## Immune Memory

Memory is append-only JSONL under `.myco/memory/`. It records scans, risks, probes, outcomes, and patch recommendations. This makes MycoPatch behavior inspectable and less dependent on any single model provider.

## Token Efficiency

The MVP runs offline and still tracks estimated token budget. Future LLM integrations should spend context only after deterministic scanning and evidence gathering have narrowed the problem.

