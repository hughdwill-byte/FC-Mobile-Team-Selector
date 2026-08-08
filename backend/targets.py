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


def compute_takeover(target: PlayerState, incumbent: PlayerState | None, position: str,
                     transfer_source: PlayerState | None = None) -> dict:
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

    # The player whose training transfers across may differ from the "bar" incumbent when
    # the formation changes (e.g. a winger being dropped funds an incoming striker).
    src = transfer_source if transfer_source is not None else incumbent
    src_level = src.training_level if src is not None else 0
    src_name = src.name if src is not None else None

    rankups: list[int] = []
    training_added = 0
    xp = 0.0
    rank_items = 0.0

    # 1. Training transfer from the source player (minus the fee).
    transferred = int(math.floor(src_level * (1 - fee)))
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
        return _result(target, incumbent, position, target_score_before, inc_score, src_level, src_name,
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
    return _result(target, incumbent, position, target_score_before, inc_score, src_level, src_name,
                   transfer_levels, rankups, training_added, xp, rank_items, tt_per_level,
                   t, achievable=achievable, reason=None if achievable else "still short even fully maxed")


def _result(target, incumbent, position, before, inc_score, src_level, src_name, transfer_levels,
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
        "transfer_from_name": src_name,
        "transfer_from_level": src_level,
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
    """Plan the transition from your ACTUAL current best XI (whatever formation) to the
    target XI (the chosen formation, with per-slot overrides). Surfaces who JOINS the team
    (with the upgrades to get them in) and who LEAVES it (e.g. a winger dropped when moving
    to a formation with no winger slot). Training from leaving players is transferred to
    joining players (minus the fee)."""
    from .optimizer import optimize

    fr = solve_named(states, formation_name)
    if fr is None:
        return {"error": f"Unknown formation: {formation_name}"}

    by_id = {s.id: s for s in states}

    # Your actual current best XI (best across all formations).
    current_best = optimize(states, top_n=1)[0]
    current_ids = {a.player_id for a in current_best.slots if a.player_id is not None}
    current_pos = {a.player_id: a.position for a in current_best.slots}

    # Normalise per-slot target overrides (keys may be strings from JSON).
    tmap = {}
    for k, v in (targets or {}).items():
        try:
            tmap[int(k)] = int(v) if v is not None else None
        except (TypeError, ValueError):
            continue

    # The target XI: each slot's chosen player (override, else the best current option for
    # this formation).
    target_slot_player = {}
    for slot in fr.slots:
        want = tmap.get(slot.slot_index)
        target_slot_player[slot.slot_index] = want if want is not None else slot.player_id
    target_ids = {pid for pid in target_slot_player.values() if pid is not None}

    # Who leaves the team on this transition (in current best XI, not in target XI).
    leaving = []
    for pid in current_ids:
        if pid not in target_ids:
            p = by_id.get(pid)
            if p is not None:
                leaving.append(p)
    leaving.sort(key=lambda p: p.training_level, reverse=True)
    leaving_pool = list(leaving)  # training-transfer sources to hand out

    # For each slot whose target player is JOINING (not already in the current best XI),
    # compute the takeover.
    takeovers = []
    for slot in fr.slots:
        pid = target_slot_player[slot.slot_index]
        if pid is None or pid in current_ids:
            continue  # empty, or the target already starts in your current best XI
        target = by_id.get(pid)
        if target is None:
            continue
        incumbent = by_id.get(slot.player_id) if slot.player_id is not None else None

        # Training-transfer source: the directly-replaced incumbent if they're leaving,
        # otherwise the highest-level leaving player still available.
        source = None
        if incumbent is not None and incumbent.id not in target_ids:
            source = incumbent
            leaving_pool[:] = [p for p in leaving_pool if p.id != incumbent.id]
        elif leaving_pool:
            source = leaving_pool.pop(0)

        res = compute_takeover(target, incumbent, slot.position, transfer_source=source)
        res["slot_index"] = slot.slot_index
        takeovers.append(res)

    takeovers.sort(key=lambda r: (not r["achievable"], r["total_cost_units"]))
    for i, t in enumerate(takeovers):
        t["order"] = i + 1

    return {
        "formation": formation_name,
        "current_best_formation": current_best.formation,
        "takeovers": takeovers,
        "leaving": [
            {"player_id": p.id, "name": p.name, "current_position": current_pos.get(p.id),
             "training_level": p.training_level, "ovr": p.ovr}
            for p in leaving
        ],
        "staying_count": len(current_ids & target_ids),
        "costs_unverified": not rules_mod.load("costs").get("verified", False),
        "transfer_fee_pct": rules_mod.load("costs").get("training_transfer", {}).get("transfer_fee_pct", 0.1),
    }
