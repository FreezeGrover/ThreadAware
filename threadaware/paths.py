from __future__ import annotations

import os
import sys
from pathlib import Path


def app_data_dir() -> Path:
    """Return a predictable per-user data directory for ThreadAware."""
    override = os.getenv("THREADAWARE_DATA_DIR")
    if override:
        path = Path(override).expanduser()
    elif sys.platform == "win32":
        root = Path(os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or Path.home())
        path = root / "ThreadAware"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "ThreadAware"
    else:
        root = Path(os.getenv("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
        path = root / "threadaware"
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    override = os.getenv("THREADAWARE_DB_PATH")
    return Path(override).expanduser() if override else app_data_dir() / "threadaware_runs.sqlite3"


def exports_dir() -> Path:
    path = app_data_dir() / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def usage_ledger_path() -> Path:
    return app_data_dir() / "token_usage.json"
