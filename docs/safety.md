# Safety

MycoPatch is local-first and offline. It does not call external APIs, start background services, run containers, or modify application source files.
Version 0.2 keeps those boundaries while adding opt-in aggressive probes.

## Command Policy

The MVP allows only:

- `python`
- `python3`
- `pytest`
- `git status`
- `git diff`

Dangerous fragments are blocked by default, including destructive filesystem commands, network tools, secret dumping patterns, cloud CLIs, Kubernetes, and privileged Docker.

## No-Network Default

The built-in spore declares `network: deny`. Future versions may add explicit capability leases for controlled network or write access, but those capabilities should be narrow, time-bounded, and auditable.

## Auditability

Generated files live under `.myco/`. Memory and cost records are append-only JSONL. Reports are Markdown so maintainers can inspect evidence without specialized infrastructure.

Aggressive probes are clearly labeled and may intentionally fail while a risky static pattern remains. They are written only under `.myco/probes/generated_tests/`, and each aggressive probe has a sibling Markdown explanation describing why it may fail and what a human should review.

## Future Capability Leases

A future capability lease should answer:

- What command or provider is being requested?
- Which paths may be read or written?
- How long does the lease last?
- What budget applies?
- What audit record will be written?
