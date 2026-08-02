"""Squad optimiser: for EVERY formation, solve the optimal assignment of players to
the 11 slots with the Hungarian algorithm (scipy.optimize.linear_sum_assignment),
then rank formations by total squad score.

Because there are only a couple of dozen formations and a few dozen players, this is
an exact solve, not an approximation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.optimize import linear_sum_assignment

from . import rules as rules_mod
from .scoring import PlayerState, slot_score


@dataclass
class SlotAssignment:
    slot_index: int
    position: str
    player_id: Optional[int]
    player_name: str
    score: float
    ovr: Optional[float]
    runner_up_id: Optional[int]
    runner_up_name: Optional[str]
    runner_up_score: Optional[float]


@dataclass
class FormationResult:
    formation: str
    total: float
    slots: list[SlotAssignment]


def _score_by_position(states: list[PlayerState], positions: list[str]) -> dict[str, np.ndarray]:
    """Precompute a score for every (player, position) pair once."""
    table: dict[str, np.ndarray] = {}
    for pos in positions:
        table[pos] = np.array([slot_score(s, pos) for s in states], dtype=float)
    return table


def solve_formation(
    states: list[PlayerState],
    formation: dict,
    score_table: dict[str, np.ndarray],
) -> FormationResult:
    slots: list[str] = formation["slots"]
    n_players = len(states)
    n_slots = len(slots)

    # Cost matrix: rows = players, cols = slots. Hungarian minimises, so cost = -score.
    # Pad with dummy players (score 0) if we have fewer than 11 players.
    n_rows = max(n_players, n_slots)
    score_matrix = np.zeros((n_rows, n_slots), dtype=float)
    for j, pos in enumerate(slots):
        col = score_table[pos]
        score_matrix[:n_players, j] = col
        # dummy rows stay 0

    cost = -score_matrix
    row_ind, col_ind = linear_sum_assignment(cost)

    # chosen[slot] = player row index (or None if a dummy filled it)
    chosen: dict[int, Optional[int]] = {}
    for r, c in zip(row_ind, col_ind):
        chosen[int(c)] = int(r) if r < n_players else None

    chosen_player_rows = {r for r in chosen.values() if r is not None}

    assignments: list[SlotAssignment] = []
    total = 0.0
    for j, pos in enumerate(slots):
        r = chosen.get(j)
        col = score_table[pos]
        # Runner-up: best-scoring player NOT already in this XI.
        ru_id = ru_name = ru_score = None
        best_ru = -1.0
        for i, st in enumerate(states):
            if i in chosen_player_rows:
                continue
            if col[i] > best_ru:
                best_ru = col[i]
                ru_id, ru_name, ru_score = st.id, st.name, float(col[i])

        if r is None:
            assignments.append(SlotAssignment(j, pos, None, "(empty)", 0.0, None, ru_id, ru_name, ru_score))
        else:
            st = states[r]
            sc = float(col[r])
            total += sc
            assignments.append(
                SlotAssignment(j, pos, st.id, st.name, sc, float(st.ovr), ru_id, ru_name, ru_score)
            )

    return FormationResult(formation=formation["name"], total=total, slots=assignments)


def optimize(states: list[PlayerState], top_n: int = 5) -> list[FormationResult]:
    formations = rules_mod.load("formations")["formations"]
    positions_needed = sorted({pos for f in formations for pos in f["slots"]})
    score_table = _score_by_position(states, positions_needed)

    results = [solve_formation(states, f, score_table) for f in formations]
    results.sort(key=lambda r: r.total, reverse=True)
    return results[:top_n]


def best_squad_score(states: list[PlayerState]) -> float:
    """Just the top squad score across all formations (used by the upgrade planner)."""
    top = optimize(states, top_n=1)
    return top[0].total if top else 0.0


def best_squad(states: list[PlayerState]) -> Optional[FormationResult]:
    top = optimize(states, top_n=1)
    return top[0] if top else None
