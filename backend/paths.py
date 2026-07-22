"""Central filesystem paths. Everything is resolved relative to the project root
so the app works no matter where it is launched from."""
from __future__ import annotations

import os
from pathlib import Path

# .../FC-Mobile-Team-Selector/backend/paths.py -> project root is two levels up
PROJECT_ROOT = Path(__file__).resolve().parent.parent

RULES_DIR = PROJECT_ROOT / "rules"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DATA_DIR = PROJECT_ROOT / "data"

# The whole database is this one file. Back it up by copying it.
# Override with the FCM_DB_PATH environment variable if you want it elsewhere.
DB_PATH = Path(os.environ.get("FCM_DB_PATH", DATA_DIR / "fcmobile.sqlite3"))


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
