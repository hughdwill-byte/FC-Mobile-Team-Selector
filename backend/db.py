"""Database layer using Python's built-in sqlite3 - no third-party packages.

JSON-ish fields (positions, playstyles, growth override) are stored as JSON text.
The whole database is a single file (see paths.DB_PATH); back it up by copying it.
"""
from __future__ import annotations

import json
import sqlite3

from .models import MAIN_STATS, Player
from .paths import DB_PATH, ensure_dirs

JSON_FIELDS = {"positions", "rankup_positions", "playstyles", "growth_override"}
COLUMNS = [
    "name", "ovr", "rank", "training_level", *MAIN_STATS,
    "positions", "rankup_positions", "playstyles", "growth_override",
    "skill_points", "notes",
]
_QCOLS = ", ".join(f'"{c}"' for c in COLUMNS)


def _connect() -> sqlite3.Connection:
    ensure_dirs()
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    con = _connect()
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            ovr INTEGER, rank INTEGER, training_level INTEGER,
            pace REAL, shooting REAL, passing REAL, dribbling REAL, defending REAL, physical REAL,
            positions TEXT, rankup_positions TEXT, playstyles TEXT, growth_override TEXT,
            skill_points INTEGER, notes TEXT
        )
        """
    )
    con.commit()
    con.close()


def _row_to_player(row: sqlite3.Row) -> Player:
    d = dict(row)
    for f in JSON_FIELDS:
        raw = d.get(f)
        if raw:
            d[f] = json.loads(raw)
        else:
            d[f] = None if f == "growth_override" else []
    return Player(**d)


def _values(p: Player) -> list:
    out = []
    for c in COLUMNS:
        v = getattr(p, c)
        if c in JSON_FIELDS:
            v = json.dumps(v) if v is not None else None
        out.append(v)
    return out


def get_all() -> list[Player]:
    con = _connect()
    rows = con.execute("SELECT * FROM players ORDER BY name COLLATE NOCASE").fetchall()
    con.close()
    return [_row_to_player(r) for r in rows]


def get(pid: int) -> Player | None:
    con = _connect()
    row = con.execute("SELECT * FROM players WHERE id = ?", (pid,)).fetchone()
    con.close()
    return _row_to_player(row) if row else None


def create(p: Player) -> Player:
    con = _connect()
    placeholders = ", ".join("?" for _ in COLUMNS)
    cur = con.execute(
        f"INSERT INTO players ({_QCOLS}) VALUES ({placeholders})", _values(p)
    )
    con.commit()
    p.id = cur.lastrowid
    con.close()
    return p


def update(pid: int, p: Player) -> Player:
    con = _connect()
    assignments = ", ".join(f'"{c}" = ?' for c in COLUMNS)
    con.execute(f"UPDATE players SET {assignments} WHERE id = ?", [*_values(p), pid])
    con.commit()
    con.close()
    p.id = pid
    return p


def delete(pid: int) -> None:
    con = _connect()
    con.execute("DELETE FROM players WHERE id = ?", (pid,))
    con.commit()
    con.close()


def delete_all() -> None:
    con = _connect()
    con.execute("DELETE FROM players")
    con.commit()
    con.close()
