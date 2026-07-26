"""Runtime configuration loader."""

from __future__ import annotations

import os
from pathlib import Path

from minions_army.core.config.defaults import DEFAULT_USER_CONFIG
from minions_army.core.config.schema import MinionsConfig


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE pairs from .env without overriding the real environment."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config(path: str | Path | None = None) -> MinionsConfig:
    """Load runtime configuration from YAML, or return schema defaults."""
    _load_dotenv()
    configured_path = path or os.environ.get("MINIONS_CONFIG_PATH")
    config_path = Path(configured_path) if configured_path else DEFAULT_USER_CONFIG
    if config_path.exists():
        return MinionsConfig.from_file(config_path)
    return MinionsConfig()


config = load_config()


def reload_config(path: str | Path | None = None) -> None:
    """Reload runtime configuration in place, from an explicit path if given."""
    config.__dict__.update(load_config(path).__dict__)
