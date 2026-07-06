# Safety

MycoPatch is local-first and offline by default. It does not call external APIs, start background services, run containers, run package managers, or modify application source files.
Version 0.4 keeps those boundaries while adding dependency-free JavaScript/TypeScript timezone probes.

## Command Policy

The MVP allows only:

- `python`
- `python3`
- `pytest`
- `node --test .myco/probes/generated_tests/*.mjs`
- `git status`
- `git diff`

Dangerous fragments are blocked by default, including destructive filesystem commands, network tools, secret dumping patterns, cloud CLIs, Kubernetes, and privileged Docker.

JavaScript/TypeScript verification uses `node --test <generated-probe.mjs>` only. Package-manager commands such as `npm`, `npx`, `yarn`, and `pnpm` are blocked in this milestone.

## No-Network Default

The built-in spore declares `network: deny`. Future versions may add explicit capability leases for controlled network or write access, but those capabilities should be narrow, time-bounded, and auditable.

Model-provider networking is also denied by default. `.myco/config.toml` starts with `default_provider = "offline"` and `allow_network_for_model_provider = false`. External model providers are never called unless that flag is explicitly changed by the user.

Provider output is advisory only and may be used for:

- summarizing failure logs
- suggesting probe ideas
- drafting patch recommendation text

Provider output must not be used for direct source-code patching in the current architecture.

## Auditability

Generated files live under `.myco/`. Memory and cost records are append-only JSONL. Reports are Markdown so maintainers can inspect evidence without specialized infrastructure.
Every model-provider call, including offline heuristic calls, is recorded in `.myco/reports/cost_ledger.jsonl`.

Aggressive probes are clearly labeled and may intentionally fail while a risky static pattern remains. They are written only under `.myco/probes/generated_tests/`, and each aggressive probe has a sibling Markdown explanation describing why it may fail and what a human should review.

JS/TS probes read the target source file as text. They do not import application modules, transpile TypeScript, install dependencies, or execute project test scripts.

## Future Capability Leases

A future capability lease should answer:

- What command or provider is being requested?
- Which paths may be read or written?
- How long does the lease last?
- What budget applies?
- What audit record will be written?
