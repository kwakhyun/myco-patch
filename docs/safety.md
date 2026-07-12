# Safety

MycoPatch is local-first and offline by default. It does not call external APIs, start background services, run containers, install dependencies, or modify application source files.
Version 0.6.1 keeps those boundaries while hardening multi-ecosystem detection and explicit-allow project verification profiles.

## Command Policy

Generated probes allow only:

- `python --version`
- `python3 --version`
- `pytest .myco/probes/generated_tests/*.py`
- `node --test .myco/probes/generated_tests/*.mjs`
- `git status`
- `git diff`

Dangerous fragments are blocked by default, including destructive filesystem commands, network tools, secret dumping patterns, cloud CLIs, Kubernetes, and privileged Docker.

Project verification profiles are separate from generated probes. `myco verify` defaults to dry-run. It only executes recognized project test profiles when the user passes `--run --allow-project-tests` or sets `allow_project_test_commands = true` in `.myco/config.toml`.

Recognized project test profiles include:

- `pytest`
- `node --test`
- `go test ./...`
- `cargo test --offline`
- `mvn test -o`
- `gradle test --offline`
- `dotnet test --no-restore`
- `bundle exec rspec`
- `vendor/bin/phpunit`

Dependency installation and network-prone commands remain blocked, including `npm`, `npx`, `yarn`, `pnpm`, `pip install`, `go get`, `cargo install`, `bundle install`, `composer install`, and `dotnet restore`.

Verification processes receive proxy-blocking and ecosystem-specific offline environment settings such as `GOPROXY=off` and `CARGO_NET_OFFLINE=true`. These settings reduce accidental downloads. They are not an OS-level network sandbox and cannot stop explicitly approved project test code from using direct sockets.

MycoPatch ignores file symlinks while scanning so repository analysis cannot follow a source or manifest link outside the repository root.

## No-Network Default

The built-in spore declares `network: deny`. Future versions may add explicit capability leases for controlled network or write access, but those capabilities should be narrow, time-bounded, and auditable.

Model-provider networking is also denied by default. External model providers require both `allow_network_for_model_provider = true` and a positive `max_cost_usd`; a zero budget blocks the call before network access.

Provider output is advisory only and may be used for:

- summarizing failure logs
- suggesting probe ideas
- drafting patch recommendation text

Provider output must not be used for direct source-code patching in the current architecture.

## Auditability

Generated files live under `.myco/`. Memory and cost records are append-only JSONL. Reports are Markdown so maintainers can inspect evidence without specialized infrastructure.
Every model-provider call, including offline heuristic calls, is recorded in `.myco/reports/cost_ledger.jsonl`.
Malformed JSONL lines are skipped during reporting and surfaced by `myco doctor` with their file and line number.

Aggressive probes are clearly labeled and may intentionally fail while a risky static pattern remains. They are written only under `.myco/probes/generated_tests/`, and each aggressive probe has a sibling Markdown explanation describing why it may fail and what a human should review.

JS/TS probes read the target source file as text. They do not import application modules, transpile TypeScript, install dependencies, or execute project test scripts.

Python bug-pattern probes for mutable defaults and broad exception swallowing also read source files as text. They do not import application modules or mutate production code.

## Guarded Patch Drafts

`myco patch --draft-diffs` is explicit opt-in. It accepts only repository-relative,
non-symlink UTF-8 source files and known deterministic transformations. Drafts are
written under `.myco/reports/patches/` as unified diffs with an original SHA-256
and rollback instructions. MycoPatch never applies these artifacts to application
source. Static-marker failures are labeled as static evidence, not behavioral proof.

Model providers do not generate guarded diffs.

Multi-ecosystem verification records `verification_dry_run`, `verification_passed`, `verification_failed`, `verification_skipped`, or `verification_blocked` memory events. Command output is sanitized so repository-specific absolute paths are replaced with `<repo-root>`.

## Future Capability Leases

A future capability lease should answer:

- What command or provider is being requested?
- Which paths may be read or written?
- How long does the lease last?
- What budget applies?
- What audit record will be written?
