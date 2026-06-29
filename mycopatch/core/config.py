from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import ValidationError

from mycopatch.core.models import ModelProviderConfig
from mycopatch.core.paths import get_paths


def load_config(repo_root: Path | str) -> ModelProviderConfig:
    paths = get_paths(repo_root)
    if not paths.config.exists():
        return ModelProviderConfig()

    try:
        raw = tomllib.loads(paths.config.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid MycoPatch config TOML at {paths.config}: {exc}") from exc

    try:
        return ModelProviderConfig.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid MycoPatch config values at {paths.config}: {exc}") from exc
