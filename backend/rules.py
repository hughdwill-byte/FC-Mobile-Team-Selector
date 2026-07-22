"""Load and save the editable rules/*.json files.

These files hold every game rule and tuning number the app relies on. Anything the
app could not verify from a free public source carries a "verified": false flag, and
the UI surfaces that as an 'UNVERIFIED' badge. Everything here can be edited from the
Rules screen (or by hand) and takes effect on the next recompute.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from .paths import RULES_DIR

RULE_FILES = [
    "positions",
    "formations",
    "stat_weights",
    "growth",
    "rankup",
    "skills",
    "playstyles",
    "costs",
    "attributes",
]


def _path(name: str):
    return RULES_DIR / f"{name}.json"


@lru_cache(maxsize=None)
def _load_cached(name: str) -> dict[str, Any]:
    with open(_path(name), "r", encoding="utf-8") as f:
        return json.load(f)


def load(name: str) -> dict[str, Any]:
    """Load a rules file (cached)."""
    if name not in RULE_FILES:
        raise KeyError(f"Unknown rules file: {name}")
    return _load_cached(name)


def save(name: str, data: dict[str, Any]) -> None:
    """Overwrite a rules file and clear the cache."""
    if name not in RULE_FILES:
        raise KeyError(f"Unknown rules file: {name}")
    with open(_path(name), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    clear_cache()


def clear_cache() -> None:
    _load_cached.cache_clear()


def all_rules() -> dict[str, Any]:
    return {name: load(name) for name in RULE_FILES}


def unverified_files() -> list[str]:
    """Names of rules files still flagged verified:false, for UI warnings."""
    out = []
    for name in RULE_FILES:
        if not load(name).get("verified", False):
            out.append(name)
    return out
