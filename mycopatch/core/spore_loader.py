from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from mycopatch.core.models import Spore
from mycopatch.core.paths import get_paths


def load_spores(repo_root: Path | str | None = None) -> list[Spore]:
    spores_by_name: dict[str, Spore] = {}
    for spore in load_builtin_spores():
        spores_by_name[spore.name] = spore

    paths = get_paths(repo_root)
    if paths.spores.exists():
        for file_path in sorted(paths.spores.glob("*.y*ml")):
            spore = load_spore_file(file_path, source="local")
            spores_by_name[spore.name] = spore

    return [spores_by_name[name] for name in sorted(spores_by_name)]


def load_builtin_spores() -> list[Spore]:
    spores: list[Spore] = []
    package_files = resources.files("mycopatch.spores")
    for spore_file in sorted(package_files.iterdir(), key=lambda item: item.name):
        if spore_file.name.endswith((".yaml", ".yml")):
            with resources.as_file(spore_file) as path:
                spores.append(load_spore_file(path, source="builtin"))
    return spores


def load_spore_file(path: Path, source: str) -> Spore:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Spore file must contain a mapping: {path}")
    payload: dict[str, Any] = dict(data)
    payload["source"] = source
    return Spore.model_validate(payload)

