from __future__ import annotations

import shutil
from dataclasses import dataclass
from importlib import resources
from pathlib import Path


MYCO_DIR = ".myco"
IGNORED_DIRS = {
    ".git",
    ".myco",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".next",
    ".nuxt",
    ".svelte-kit",
    ".turbo",
    "coverage",
    "out",
    "vendor",
    "target",
    ".gradle",
    "bin",
    "obj",
}

MEMORY_FILES = [
    "failure_patterns.jsonl",
    "accepted_patches.jsonl",
    "rejected_patches.jsonl",
    "negative_results.jsonl",
]

DEFAULT_CONSTITUTION = """# Repo Constitution

MycoPatch is allowed to inspect this repository, generate safe probes under `.myco/`,
run explicitly allowed local verification commands, and record append-only memory.

Default boundaries:

- No network access.
- No secret exfiltration.
- No destructive commands.
- No arbitrary source modification.
- Patches are recommendations unless a maintainer explicitly applies them.
"""

DEFAULT_CONFIG = """# MycoPatch configuration

# Offline heuristic mode is the default. External model providers are never
# called unless allow_network_for_model_provider is explicitly set to true.
default_provider = "offline"
model_name = "offline-heuristic"
max_input_tokens = 6000
max_output_tokens = 1200
max_cost_usd = 0.0
allow_network_for_model_provider = false
allow_project_test_commands = false

# Optional for provider interfaces. Leave blank to keep offline-only behavior.
provider_base_url = ""
api_key_env = "OPENAI_API_KEY"
"""


@dataclass(frozen=True)
class MycoPaths:
    repo_root: Path

    @property
    def myco(self) -> Path:
        return self.repo_root / MYCO_DIR

    @property
    def memory(self) -> Path:
        return self.myco / "memory"

    @property
    def spores(self) -> Path:
        return self.myco / "spores"

    @property
    def probes(self) -> Path:
        return self.myco / "probes"

    @property
    def generated_tests(self) -> Path:
        return self.probes / "generated_tests"

    @property
    def reports(self) -> Path:
        return self.myco / "reports"

    @property
    def config(self) -> Path:
        return self.myco / "config.toml"

    @property
    def constitution(self) -> Path:
        return self.memory / "repo_constitution.md"

    @property
    def repo_weather(self) -> Path:
        return self.reports / "repo_weather.md"

    @property
    def cost_ledger(self) -> Path:
        return self.reports / "cost_ledger.jsonl"

    @property
    def immune_history(self) -> Path:
        return self.reports / "immune_history.md"

    @property
    def patch_recommendations(self) -> Path:
        return self.reports / "patch_recommendations.md"


def get_paths(repo_root: Path | str | None = None) -> MycoPaths:
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    return MycoPaths(root.resolve())


def is_initialized(repo_root: Path | str | None = None) -> bool:
    return get_paths(repo_root).myco.is_dir()


def ensure_myco_layout(repo_root: Path | str | None = None) -> MycoPaths:
    paths = get_paths(repo_root)
    for directory in [
        paths.memory,
        paths.spores,
        paths.generated_tests,
        paths.reports,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    if not paths.constitution.exists():
        paths.constitution.write_text(DEFAULT_CONSTITUTION, encoding="utf-8")
    if not paths.config.exists():
        paths.config.write_text(DEFAULT_CONFIG, encoding="utf-8")

    for filename in MEMORY_FILES:
        (paths.memory / filename).touch(exist_ok=True)
    paths.cost_ledger.touch(exist_ok=True)

    copy_builtin_spores(paths)
    return paths


def copy_builtin_spores(paths: MycoPaths) -> list[Path]:
    copied: list[Path] = []
    package_files = resources.files("mycopatch.spores")
    for spore in sorted(package_files.iterdir(), key=lambda item: item.name):
        if spore.name.endswith((".yaml", ".yml")):
            target = paths.spores / spore.name
            if not target.exists():
                with resources.as_file(spore) as spore_path:
                    shutil.copyfile(spore_path, target)
                copied.append(target)
    return copied
