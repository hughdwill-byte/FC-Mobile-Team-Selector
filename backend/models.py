"""Database models (SQLModel). The entire collection lives in one SQLite file.

A note on how stats are stored: you enter each player's SIX MAIN STATS exactly as
they currently appear in-game (pace/shooting/passing/dribbling/defending/physical),
plus OVR, training level and rank. The optimiser and the upgrade planner then
*simulate* upgrades using the growth / rank-up / skill rules, without you having to
re-enter anything.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

MAIN_STATS = ["pace", "shooting", "passing", "dribbling", "defending", "physical"]


class Player(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)

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
    positions: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    # Positions that become eligible on the NEXT rank up (unlock mechanic). Optional.
    rankup_positions: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    # Up to two play styles: [{"name": "Rapid", "plus": false}, ...]
    playstyles: list[dict] = Field(default_factory=list, sa_column=Column(JSON))

    # Optional per-player growth override: {"pace": 0.6, ...}. Null -> use rules/growth.json default.
    growth_override: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    # Unspent skill points available to allocate.
    skill_points: int = 0

    notes: str = ""


class PlayerRead(SQLModel):
    """Shape returned to the frontend."""
    id: int
    name: str
    ovr: int
    rank: int
    training_level: int
    pace: float
    shooting: float
    passing: float
    dribbling: float
    defending: float
    physical: float
    positions: list[str]
    rankup_positions: list[str]
    playstyles: list[dict]
    growth_override: Optional[dict]
    skill_points: int
    notes: str


class PlayerCreate(SQLModel):
    name: str
    ovr: int = 50
    rank: int = 0
    training_level: int = 0
    pace: float = 50
    shooting: float = 50
    passing: float = 50
    dribbling: float = 50
    defending: float = 50
    physical: float = 50
    positions: list[str] = []
    rankup_positions: list[str] = []
    playstyles: list[dict] = []
    growth_override: Optional[dict] = None
    skill_points: int = 0
    notes: str = ""
