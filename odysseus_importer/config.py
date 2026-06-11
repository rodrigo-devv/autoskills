"""Persist user preferences (the Odysseus root path) between runs.

The cache lives in the platform's user-config directory:
``%APPDATA%\\odysseus-importer`` on Windows, ``$XDG_CONFIG_HOME`` or
``~/.config/odysseus-importer`` elsewhere. Caching is best-effort —
failures to read or write the file are silently ignored.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "odysseus-importer"


def config_file() -> Path:
    """Path of the JSON config file for the current platform."""
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else Path.home() / ".config"
    return base / APP_NAME / "config.json"


def load_cached_root() -> str | None:
    """Return the cached Odysseus root path, or ``None`` if not cached."""
    try:
        data = json.loads(config_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    root = data.get("odysseus_root") if isinstance(data, dict) else None
    return root if isinstance(root, str) and root else None


def save_cached_root(root: Path) -> None:
    """Remember *root* for the next run."""
    target = config_file()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps({"odysseus_root": str(root)}, indent=2), encoding="utf-8"
        )
    except OSError:
        pass
