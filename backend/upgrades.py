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
from .scoring import (
    PlayerState,
    priority_stats,
    with_rankup,
    with_skill_point,
    with_training_level,
)


def _swap(states: list[PlayerState], index: int, new_state: PlayerState) -> list[PlayerState]:
    out = list(states)
    out[index] = new_state
    return out


def plan_training_budget(states: list[PlayerState], xp_budget: float, max_steps: int = 300) -> dict:
    """Given an XP budget, return the best ORDERED sequence of training to spend it on.

    Greedy: at each step, look at 'train one more level' for every player, pick the one
    with the best squad-score gain per XP that we can still afford, apply it, and repeat
    until the budget can't buy another worthwhile level. This naturally spreads XP across
    players (and levels) in best-value order rather than dumping it all on one card.
    """
    costs = rules_mod.load("costs")
    training_costs = costs["training"]["per_level"]
    max_level = rules_mod.load("growth").get("max_training_level", 30)

    def level_cost(lvl: int) -> float:
        return training_costs[lvl] if lvl < len(training_costs) else training_costs[-1]

    work = [s.copy() for s in states]
    baseline = current = best_squad_score(work)
    remaining = float(xp_budget)
    raw: list[dict] = []

    for _ in range(max_steps):
        best = None  # (gpc, gain, cost, idx, from_level, new_state, new_score)
        for idx, st in enumerate(work):
            lvl = st.training_level
            if lvl >= max_level:
                continue
            cost = level_cost(lvl)
            if cost > remaining:
                continue
            ns = with_training_level(st, 1)
            if ns is None:
                continue
            score = best_squad_score(_swap(work, idx, ns))
            gain = score - current
            if gain <= 1e-9:
                continue
            gpc = gain / cost
            if best is None or gpc > best[0]:
                best = (gpc, gain, cost, idx, lvl, ns, score)

        if best is None:
            break
        _gpc, gain, cost, idx, lvl, ns, score = best
        work[idx] = ns
        current = score
        remaining -= cost
        raw.append({
            "player_id": ns.id, "player_name": ns.name,
            "from_level": lvl, "to_level": lvl + 1, "gain": gain, "cost": cost,
        })

    # Why did we stop? (budget ran out vs. no more worthwhile training)
    reason = "no_more_value"
    if len(raw) < max_steps:
        for idx, st in enumerate(work):
            lvl = st.training_level
            if lvl >= max_level:
                continue
            ns = with_training_level(st, 1)
            if ns is None:
                continue
            if best_squad_score(_swap(work, idx, ns)) - current > 1e-9:
                reason = "budget"   # a worthwhile level exists, we just can't afford it
                break
    else:
        reason = "step_cap"

    # Merge consecutive levels for the same player into a single "L -> M" row.
    merged: list[dict] = []
    for s in raw:
        if merged and merged[-1]["player_id"] == s["player_id"] and merged[-1]["to_level"] == s["from_level"]:
            merged[-1]["to_level"] = s["to_level"]
            merged[-1]["gain"] += s["gain"]
            merged[-1]["cost"] += s["cost"]
        else:
            merged.append(dict(s))

    cum_xp = cum_gain = 0.0
    for m in merged:
        cum_xp += m["cost"]
        cum_gain += m["gain"]
        m["cumulative_xp"] = round(cum_xp)
        m["cumulative_gain"] = round(cum_gain, 3)
        m["gain"] = round(m["gain"], 3)
        m["cost"] = round(m["cost"])
        m["levels"] = m["to_level"] - m["from_level"]
        m["gain_per_cost"] = round((m["gain"] / m["cost"]) if m["cost"] else 0.0, 5)

    return {
        "xp_budget": round(float(xp_budget)),
        "spent": round(float(xp_budget) - remaining),
        "remaining": round(remaining),
        "baseline_squad_score": round(baseline, 3),
        "final_squad_score": round(current, 3),
        "total_gain": round(current - baseline, 3),
        "levels_trained": sum(m["levels"] for m in merged),
        "steps": merged,
        "stopped_reason": reason,
        "costs_unverified": not costs.get("verified", False),
    }


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

        # Skill points: invest in the player's priority stat (their PlayStyle-boosted
        # stats first, then their position's key stats - see scoring.priority_stats).
        if st.skill_points > 0:
            stat = priority_stats(st)[0]
            ns = with_skill_point(st, stat)
            add("skill", idx, st, ns, skill_cost,
                f"Spend 1 skill point on {st.name} ({stat})",
                f"+skill to {stat} (priority stat for {st.positions[0] if st.positions else 'player'})")

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
