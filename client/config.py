from __future__ import annotations

import os
import tomllib  # stdlib in Python 3.11+
from pathlib import Path
from typing import Any


def _load_env_file(path: Path) -> dict[str, str]:
    """Parse a simple .env file. Return empty dict if file does not exist."""
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        result[key] = value
    return result


def _load_toml(path: Path) -> dict[str, Any]:
    """Load a TOML file using tomllib.load(). Return empty dict if file does not exist."""
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def load_config() -> dict[str, Any]:
    """Load and merge config from .env and TOML files, returning the merged config."""
    # 1. Load and merge .env files into os.environ using os.environ.setdefault()
    for env_path in (Path(".env"), Path.home() / ".ads-transparency.env"):
        for key, value in _load_env_file(env_path).items():
            os.environ.setdefault(key, value)

    # 2. Load and merge TOML config files (later file overrides earlier)
    global_config = _load_toml(
        Path.home() / ".config" / "ads-transparency" / "config.toml"
    )
    local_config = _load_toml(Path("ads-transparency.toml"))
    merged: dict[str, Any] = {}
    merged.update(global_config)
    merged.update(local_config)
    return merged


_config: dict[str, Any] | None = None


def get_config() -> dict[str, Any]:
    """Module-level cache: load once, return the same dict on subsequent calls."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def get(section: str, key: str, default: Any = None) -> Any:
    """Convenience accessor: return config[section][key] if it exists, else default."""
    config = get_config()
    section_data = config.get(section)
    if not isinstance(section_data, dict):
        return default
    return section_data.get(key, default)


def write_sample_config(path: Path) -> None:
    """Write a sample config file to path."""
    content = """[ai]
# AI provider to use: groq, openai, anthropic, ollama, together, or custom
provider = "groq"
# model is auto-detected from the provider's /models endpoint if omitted
# model = "qwen/qwen3.8-27b"

[client]
timeout = 20
min_interval = 0.25
max_retries = 3
# proxy = "http://user:pass@proxy:8080"
# proxies = ["http://p1:8080", "http://p2:8080"]

[cli]
# default output format: table, json, csv, or xlsx
format = "table"
# default pages to fetch
pages = 1
# default limit for download-previews
limit = 50
"""
    path.write_text(content, encoding="utf-8")


def write_sample_env(path: Path) -> None:
    """Write a sample .env file."""
    content = """# Google Ads Transparency Client - API Keys
# Uncomment and fill in the keys you need

# GROQ_API_KEY=gsk_...
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# TOGETHER_API_KEY=...

# Override defaults
# AI_PROVIDER=groq
# AI_MODEL=
# AI_BASE_URL=
"""
    path.write_text(content, encoding="utf-8")
