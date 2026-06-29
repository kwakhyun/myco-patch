# Safety

MycoPatch v0.1 is local-first and offline. It does not call external APIs, start background services, run containers, or modify application source files.

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

## Future Capability Leases

A future capability lease should answer:

- What command or provider is being requested?
- Which paths may be read or written?
- How long does the lease last?
- What budget applies?
- What audit record will be written?

