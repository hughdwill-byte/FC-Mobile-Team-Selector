"""Helpers to turn DB rows / dataclasses into JSON-friendly dicts."""
from __future__ import annotations

from dataclasses import asdict

from .models import MAIN_STATS, Player
from .optimizer import FormationResult
from .scoring import best_position_score, effective_stats, player_to_state


def player_out(p: Player) -> dict:
    st = player_to_state(p)
    best_pos, best_score = best_position_score(st)
    eff = effective_stats(st)
    return {
        "id": p.id,
        "name": p.name,
        "ovr": p.ovr,
        "rank": p.rank,
        "training_level": p.training_level,
        **{s: getattr(p, s) for s in MAIN_STATS},
        "effective_stats": {k: round(v, 1) for k, v in eff.items()},
        "positions": p.positions or [],
        "rankup_positions": p.rankup_positions or [],
        "playstyles": p.playstyles or [],
        "growth_override": p.growth_override,
        "skill_points": p.skill_points,
        "notes": p.notes or "",
        "best_position": best_pos,
        "best_score": round(best_score, 2),
    }


def formation_out(fr: FormationResult) -> dict:
    return asdict(fr)
