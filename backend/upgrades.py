"""Upgrade planner.

For every possible NEXT upgrade (one training level, one rank up, or one skill point),
simulate it, recompute the best squad score across all formations, and measure the
marginal gain. Rank by gain-per-cost.

Because upgrading a player who is NOT currently in the XI can flip them into it, we
always re-solve the full optimiser for each candidate rather than only looking at
players already in the team.
"""
from __future__ import annotations

from . import rules as rules_mod
from .models import MAIN_STATS
from .optimizer import best_squad_score
from .scoring import PlayerState, with_rankup, with_skill_point, with_training_level


def _swap(states: list[PlayerState], index: int, new_state: PlayerState) -> list[PlayerState]:
    out = list(states)
    out[index] = new_state
    return out


def plan_upgrades(states: list[PlayerState], limit: int = 40) -> dict:
    costs = rules_mod.load("costs")
    training_costs = costs["training"]["per_level"]
    rankup_costs = costs["rankup"]["per_rank"]
    skill_cost = costs["skill"]["per_point"]
    norm = costs.get("normalization", {})
    unit = {
        "training": norm.get("training_unit", 1.0),
        "rankup": norm.get("rankup_unit", 1.0),
        "skill": norm.get("skill_unit", 1.0),
    }

    baseline = best_squad_score(states)
    candidates: list[dict] = []

    def add(kind, idx, state, new_state, raw_cost, label, detail):
        if new_state is None:
            return
        new_score = best_squad_score(_swap(states, idx, new_state))
        gain = new_score - baseline
        combined_cost = raw_cost * unit[kind]
        gpc = (gain / combined_cost) if combined_cost > 0 else 0.0
        candidates.append({
            "kind": kind,
            "player_id": state.id,
            "player_name": state.name,
            "label": label,
            "detail": detail,
            "gain": round(gain, 3),
            "raw_cost": raw_cost,
            "cost_currency": {"training": "XP", "rankup": "rank items", "skill": "skill points"}[kind],
            "combined_cost": round(combined_cost, 2),
            "gain_per_cost": round(gpc, 5),
            "new_squad_score": round(new_score, 3),
        })

    for idx, st in enumerate(states):
        # Training +1 level.
        if st.training_level < rules_mod.load("growth").get("max_training_level", 30):
            lvl = st.training_level
            raw = training_costs[lvl] if lvl < len(training_costs) else training_costs[-1]
            add("training", idx, st, with_training_level(st, 1), raw,
                f"Train {st.name} to level {lvl + 1}",
                f"Training level {lvl} -> {lvl + 1}")

        # Rank up.
        max_rank = rules_mod.load("rankup").get("max_rank", 5)
        if st.rank < max_rank:
            raw = rankup_costs[st.rank] if st.rank < len(rankup_costs) else rankup_costs[-1]
            add("rankup", idx, st, with_rankup(st), raw,
                f"Rank up {st.name} to rank {st.rank + 1}",
                f"Rank {st.rank} -> {st.rank + 1}")

        # Skill points (only surface the best-value stat per player to avoid noise).
        if st.skill_points > 0:
            best = None
            for stat in MAIN_STATS:
                ns = with_skill_point(st, stat)
                if ns is None:
                    continue
                sc = best_squad_score(_swap(states, idx, ns))
                if best is None or sc > best[1]:
                    best = (stat, sc, ns)
            if best is not None:
                stat, _, ns = best
                add("skill", idx, st, ns, skill_cost,
                    f"Spend 1 skill point on {st.name} ({stat})",
                    f"+skill to {stat}")

    positive = [c for c in candidates if c["gain"] > 1e-9]
    positive.sort(key=lambda c: (c["gain_per_cost"], c["gain"]), reverse=True)

    by_kind = {}
    for kind in ("training", "rankup", "skill"):
        ranked = [c for c in positive if c["kind"] == kind]
        by_kind[kind] = ranked[:limit]

    return {
        "baseline_squad_score": round(baseline, 3),
        "combined": positive[:limit],
        "by_kind": by_kind,
        "zero_gain_count": len(candidates) - len(positive),
        "costs_unverified": not costs.get("verified", False),
    }
