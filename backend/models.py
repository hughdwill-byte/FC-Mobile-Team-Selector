"""Data model - plain Python dataclasses, no third-party ORM.

The whole collection lives in one SQLite file, using Python's built-in `sqlite3`
module (see db.py). Nothing here needs to be installed.

A note on how stats are stored: you enter each player's SIX MAIN STATS exactly as
they currently appear in-game (pace/shooting/passing/dribbling/defending/physical),
plus OVR, training level and rank. The optimiser and the upgrade planner then
*simulate* upgrades using the growth / rank-up / skill rules, without you having to
re-enter anything.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

MAIN_STATS = ["pace", "shooting", "passing", "dribbling", "defending", "physical"]

# Fields a client is allowed to set on a player (everything except the id).
EDITABLE_FIELDS = [
    "name", "ovr", "rank", "training_level", *MAIN_STATS,
    "base_stats",
    "positions", "rankup_positions", "playstyles",
    "growth_override", "skill_points", "notes",
]


@dataclass
class Player:
    name: str = ""
    ovr: int = 50
    rank: int = 0                 # 0..5  (times OVR has been ranked up)
    training_level: int = 0       # 0..30

    # Current main stats, as shown in-game right now.
    pace: float = 50
    shooting: float = 50
    passing: float = 50
    dribbling: float = 50
    defending: float = 50
    physical: float = 50

    # Eligible positions, e.g. ["ST", "CF"]. First entry is treated as the natural one.
    positions: list = field(default_factory=list)
    # Positions that become eligible on the NEXT rank up (unlock mechanic). Optional.
    rankup_positions: list = field(default_factory=list)
    # Up to two play styles: [{"name": "Rapid", "plus": false}, ...]
    playstyles: list = field(default_factory=list)
    # Base stats at training level 0 (the fair way to compare cards, since current stats
    # depend on how much a player has been trained). Optional dict {"pace": 70, ...}.
    base_stats: Optional[dict] = None
    # Optional per-player growth override: {"pace": 0.6, ...}. None -> use rules/growth.json.
    growth_override: Optional[dict] = None
    # Unspent skill points available to allocate.
    skill_points: int = 0
    notes: str = ""

    id: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _coerce(field_name: str, value):
    """Light coercion so numbers arriving as strings/None still land sensibly."""
    if value is None:
        return None
    if field_name in ("ovr", "rank", "training_level", "skill_points"):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0
    if field_name in MAIN_STATS:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    return value


def player_from_dict(data: dict, base: Optional[Player] = None) -> Player:
    """Build a Player from client JSON, or update `base` in place-ish."""
    p = base or Player()
    for k in EDITABLE_FIELDS:
        if k in data and data[k] is not None:
            setattr(p, k, _coerce(k, data[k]))
    return p
