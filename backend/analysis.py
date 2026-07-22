"""Gap report + bench view."""
from __future__ import annotations

from .optimizer import FormationResult, best_squad
from .scoring import PlayerState, best_position_score


def gap_report(states: list[PlayerState], squad: FormationResult | None = None) -> dict:
    """For each slot in the current best formation, report how weak it is relative to
    the rest of the squad and flag slots with no genuine specialist / only an
    out-of-position option. Returns slots ordered by investment priority."""
    if squad is None:
        squad = best_squad(states)
    if squad is None:
        return {"formation": None, "slots": [], "priority_positions": []}

    by_id = {s.id: s for s in states}
    naturally_covers = {}
    for pos_set in (s.positions for s in states):
        for pos in pos_set:
            naturally_covers[pos] = naturally_covers.get(pos, 0) + 1

    squad_avg = squad.total / len(squad.slots) if squad.slots else 0.0

    rows = []
    for a in squad.slots:
        st = by_id.get(a.player_id)
        out_of_pos = bool(st and a.position not in st.positions)
        no_specialist = naturally_covers.get(a.position, 0) == 0
        deficit = squad_avg - a.score              # >0 => below squad average
        depth_gap = a.score - (a.runner_up_score or 0.0)  # big => no backup
        priority = deficit + (6.0 if out_of_pos else 0.0) + (4.0 if no_specialist else 0.0)

        reasons = []
        if out_of_pos:
            reasons.append("filled by an out-of-position player")
        if no_specialist:
            reasons.append("no natural specialist in your club")
        if deficit > 0:
            reasons.append(f"{deficit:.1f} below squad average")
        if depth_gap > 15:
            reasons.append("no real backup (thin depth)")
        if not reasons:
            reasons.append("solid")

        rows.append({
            "slot_index": a.slot_index,
            "position": a.position,
            "player_name": a.player_name,
            "score": round(a.score, 2),
            "out_of_position": out_of_pos,
            "no_specialist": no_specialist,
            "deficit_vs_avg": round(deficit, 2),
            "depth_gap": round(depth_gap, 2),
            "priority": round(priority, 2),
            "reasons": reasons,
        })

    priority_sorted = sorted(rows, key=lambda r: r["priority"], reverse=True)
    priority_positions = [
        {"position": r["position"], "priority": r["priority"], "reasons": r["reasons"]}
        for r in priority_sorted if r["priority"] > 0.5
    ]

    return {
        "formation": squad.formation,
        "squad_average": round(squad_avg, 2),
        "slots": rows,
        "priority_positions": priority_positions,
    }


def bench_view(states: list[PlayerState], squad: FormationResult | None = None, size: int = 7) -> list[dict]:
    """The next-best `size` players not in the starting XI, with their best position.
    No optimisation - just visibility."""
    if squad is None:
        squad = best_squad(states)
    xi_ids = {a.player_id for a in squad.slots} if squad else set()

    rows = []
    for st in states:
        if st.id in xi_ids:
            continue
        pos, score = best_position_score(st)
        rows.append({
            "player_id": st.id,
            "player_name": st.name,
            "ovr": st.ovr,
            "best_position": pos,
            "best_score": round(score, 2),
            "positions": st.positions,
        })
    rows.sort(key=lambda r: r["best_score"], reverse=True)
    return rows[:size]
