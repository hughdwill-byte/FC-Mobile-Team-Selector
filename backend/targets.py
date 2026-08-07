"""Target-team takeover planner.

You pick a target XI (a formation + the player you WANT in each slot). For every slot
where your target differs from who currently wins it, this works out the cheapest path
for your target player to take over that slot:

  1. Training transfer - the incumbent's training level moves to your target, minus a
     transfer fee (default 10%), per rules/costs.json.
  2. Rank ups - if your target can't yet play the position, rank them up until it unlocks
     (and for the OVR boost).
  3. Training - top up training levels until your target's slot score reaches the incumbent.

Results are split into a rank-up section and a training section, ordered by which target
can take over most cheaply (i.e. soonest).
"""
from __future__ import annotations

import math

from . import rules as rules_mod
from .optimizer import solve_named
from .scoring import PlayerState, slot_score, with_rankup, with_training_level


def _norm_cost(xp: float, rank_items: float) -> float:
    norm = rules_mod.load("costs").get("normalization", {})
    return xp * norm.get("training_unit", 1.0) + rank_items * norm.get("rankup_unit", 1.0)


def compute_takeover(target: PlayerState, incumbent: PlayerState | None, position: str) -> dict:
    costs = rules_mod.load("costs")
    training_costs = costs["training"]["per_level"]
    rankup_costs = costs["rankup"]["per_rank"]
    fee = costs.get("training_transfer", {}).get("transfer_fee_pct", 0.1)
    tt_per_level = costs.get("training_transfer", {}).get("tt_point_cost_per_level", 1)
    max_level = rules_mod.load("growth").get("max_training_level", 30)
    max_rank = rules_mod.load("rankup").get("max_rank", 5)

    def lvl_cost(lvl: int) -> float:
        return training_costs[lvl] if lvl < len(training_costs) else training_costs[-1]

    def rank_cost(rank: int) -> float:
        return rankup_costs[rank] if rank < len(rankup_costs) else rankup_costs[-1]

    t = target.copy()
    target_score_before = slot_score(t, position)
    inc_score = slot_score(incumbent, position) if incumbent is not None else 0.0
    inc_level = incumbent.training_level if incumbent is not None else 0

    rankups: list[int] = []
    training_added = 0
    xp = 0.0
    rank_items = 0.0

    # 1. Training transfer from the incumbent (minus the fee).
    transferred = int(math.floor(inc_level * (1 - fee)))
    transfer_levels = 0
    if transferred > t.training_level:
        add = transferred - t.training_level
        nt = with_training_level(t, add)
        if nt is not None:
            t = nt
            transfer_levels = add

    # 2. Rank up until the position is unlocked (if needed).
    guard = 0
    while position not in t.positions and t.rank < max_rank and guard < 12:
        nr = with_rankup(t)
        if nr is None:
            break
        rank_items += rank_cost(t.rank)
        rankups.append(t.rank + 1)
        t = nr
        guard += 1

    if position not in t.positions:
        return _result(target, incumbent, position, target_score_before, inc_score, inc_level,
                       transfer_levels, rankups, training_added, xp, rank_items, tt_per_level,
                       t, achievable=False, reason="cannot play this position even fully ranked up")

    # 3. Top up (training levels / rank ups) until we reach the incumbent's slot score.
    guard = 0
    while slot_score(t, position) < inc_score - 1e-9 and guard < 80:
        best = None  # (gain_per_cost, kind, new_state, cost)
        cur = slot_score(t, position)
        if t.training_level < max_level:
            c = lvl_cost(t.training_level)
            nt = with_training_level(t, 1)
            if nt is not None:
                g = slot_score(nt, position) - cur
                best = (g / c if c else 0.0, "train", nt, c)
        if t.rank < max_rank:
            c = rank_cost(t.rank)
            nr = with_rankup(t)
            if nr is not None:
                g = slot_score(nr, position) - cur
                cand = (g / c if c else 0.0, "rank", nr, c)
                if best is None or cand[0] > best[0]:
                    best = cand
        if best is None:
            break  # fully maxed and still short
        _, kind, nstate, c = best
        if kind == "train":
            training_added += 1
            xp += c
        else:
            rank_items += c
            rankups.append(t.rank + 1)
        t = nstate
        guard += 1

    achievable = slot_score(t, position) >= inc_score - 1e-9
    return _result(target, incumbent, position, target_score_before, inc_score, inc_level,
                   transfer_levels, rankups, training_added, xp, rank_items, tt_per_level,
                   t, achievable=achievable, reason=None if achievable else "still short even fully maxed")


def _result(target, incumbent, position, before, inc_score, inc_level, transfer_levels,
            rankups, training_added, xp, rank_items, tt_per_level, final, achievable, reason) -> dict:
    return {
        "position": position,
        "target_id": target.id,
        "target_name": target.name,
        "incumbent_id": incumbent.id if incumbent is not None else None,
        "incumbent_name": incumbent.name if incumbent is not None else "(empty)",
        "incumbent_score": round(inc_score, 2),
        "target_score_before": round(before, 2),
        "target_score_after": round(slot_score(final, position), 2),
        "transfer_from_level": inc_level,
        "transfer_levels": transfer_levels,
        "tt_points": transfer_levels * tt_per_level,
        "rankups": rankups,
        "rank_from": target.rank,
        "final_rank": final.rank,
        "rank_items": round(rank_items),
        "training_added": training_added,
        "final_level": final.training_level,
        "xp": round(xp),
        "total_cost_units": round(_norm_cost(xp, rank_items), 2),
        "achievable": achievable,
        "reason": reason,
    }


def takeover_plan(states: list[PlayerState], formation_name: str, targets: dict) -> dict:
    fr = solve_named(states, formation_name)
    if fr is None:
        return {"error": f"Unknown formation: {formation_name}"}

    by_id = {s.id: s for s in states}
    # Normalise target keys to ints (they may arrive as strings from JSON).
    tmap = {}
    for k, v in (targets or {}).items():
        try:
            tmap[int(k)] = int(v) if v is not None else None
        except (TypeError, ValueError):
            continue

    takeovers = []
    for slot in fr.slots:
        want = tmap.get(slot.slot_index)
        if want is None or want == slot.player_id:
            continue  # slot unchanged
        target = by_id.get(want)
        if target is None:
            continue
        incumbent = by_id.get(slot.player_id) if slot.player_id is not None else None
        res = compute_takeover(target, incumbent, slot.position)
        res["slot_index"] = slot.slot_index
        takeovers.append(res)

    # Quickest (cheapest) achievable takeovers first; unachievable last.
    takeovers.sort(key=lambda r: (not r["achievable"], r["total_cost_units"]))
    for i, t in enumerate(takeovers):
        t["order"] = i + 1

    return {
        "formation": formation_name,
        "takeovers": takeovers,
        "costs_unverified": not rules_mod.load("costs").get("verified", False),
        "transfer_fee_pct": rules_mod.load("costs").get("training_transfer", {}).get("transfer_fee_pct", 0.1),
    }
