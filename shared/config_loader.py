# shared/config_loader.py
"""Utility to load configuration files (YAML or JSON) with environment variable overrides.

Typical usage:
```python
from shared.config_loader import load_config
config = load_config('settings.yaml')
```
The function searches in the `config/` directory at the repository root.
"""
import os
import json
from pathlib import Path
from typing import Any, Dict

import yaml  # PyYAML is a dependency

CONFIG_ROOT = Path(__file__).resolve().parents[1] / "config"

def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_config(filename: str) -> Dict[str, Any]:
    """Load a configuration file from the `config/` directory.

    Supports ``.yaml``, ``.yml``, and ``.json`` extensions. After loading the file, any
    environment variable that matches a top‑level key (case‑insensitive) will override the
    value from the file.
    """
    config_path = CONFIG_ROOT / filename
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    if config_path.suffix in {".yaml", ".yml"}:
        data = _load_yaml(config_path)
    elif config_path.suffix == ".json":
        data = _load_json(config_path)
    else:
        raise ValueError(f"Unsupported config file type: {config_path.suffix}")

    # Override with environment variables (upper‑case keys only)
    for key in list(data.keys()):
        env_val = os.getenv(key.upper())
        if env_val is not None:
            try:
                data[key] = json.loads(env_val)
            except json.JSONDecodeError:
                data[key] = env_val
    return data
