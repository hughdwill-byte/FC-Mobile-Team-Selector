"""CSV import/export for bulk editing player collections in a spreadsheet."""
from __future__ import annotations

import csv
import io

from .models import MAIN_STATS, Player

BASE_COLS = [f"base_{s}" for s in MAIN_STATS]
CSV_COLUMNS = [
    "name", "ovr", "rank", "training_level",
    *MAIN_STATS,
    *BASE_COLS,          # base stats at level 0 (blank = not set)
    "positions",         # pipe-separated, e.g. ST|CF
    "rankup_positions",  # pipe-separated
    "playstyles",        # pipe-separated, '+' suffix marks PlayStyle+, e.g. Rapid+|Finesse Expert
    "skill_points",
    "notes",
]


def _fmt_playstyles(playstyles: list[dict]) -> str:
    parts = []
    for ps in playstyles or []:
        name = ps.get("name", "")
        parts.append(name + ("+" if ps.get("plus") else ""))
    return "|".join(parts)


def _parse_playstyles(text: str) -> list[dict]:
    out = []
    for raw in (text or "").split("|"):
        raw = raw.strip()
        if not raw:
            continue
        plus = raw.endswith("+")
        name = raw[:-1].strip() if plus else raw
        out.append({"name": name, "plus": plus})
    return out


def export_csv(players: list[Player]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLUMNS)
    w.writeheader()
    for p in players:
        row = {
            "name": p.name,
            "ovr": p.ovr,
            "rank": p.rank,
            "training_level": p.training_level,
            **{s: getattr(p, s) for s in MAIN_STATS},
            **{f"base_{s}": (p.base_stats or {}).get(s, "") for s in MAIN_STATS},
            "positions": "|".join(p.positions or []),
            "rankup_positions": "|".join(p.rankup_positions or []),
            "playstyles": _fmt_playstyles(p.playstyles or []),
            "skill_points": p.skill_points,
            "notes": p.notes or "",
        }
        w.writerow(row)
    return buf.getvalue()


def parse_csv(text: str) -> list[Player]:
    reader = csv.DictReader(io.StringIO(text))
    players = []
    for row in reader:
        if not (row.get("name") or "").strip():
            continue

        def num(key, cast=float, default=0):
            v = (row.get(key) or "").strip()
            try:
                return cast(v)
            except (ValueError, TypeError):
                return default

        base = {}
        for s in MAIN_STATS:
            v = (row.get(f"base_{s}") or "").strip()
            if v != "":
                try:
                    base[s] = float(v)
                except ValueError:
                    pass

        players.append(Player(
            name=row["name"].strip(),
            ovr=num("ovr", int, 50),
            rank=num("rank", int, 0),
            training_level=num("training_level", int, 0),
            pace=num("pace", float, 50),
            shooting=num("shooting", float, 50),
            passing=num("passing", float, 50),
            dribbling=num("dribbling", float, 50),
            defending=num("defending", float, 50),
            physical=num("physical", float, 50),
            base_stats=base or None,
            positions=[x.strip() for x in (row.get("positions") or "").split("|") if x.strip()],
            rankup_positions=[x.strip() for x in (row.get("rankup_positions") or "").split("|") if x.strip()],
            playstyles=_parse_playstyles(row.get("playstyles", "")),
            skill_points=num("skill_points", int, 0),
            notes=(row.get("notes") or "").strip(),
        ))
    return players
