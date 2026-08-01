"""Scoring: how good is a player in a given position slot.

This is THE swappable scoring function referenced in the build spec. Squad score is
just the sum of per-slot scores, so everything about "what makes a good squad" lives
here and in the editable rules files (stat_weights.json, positions.json, playstyles.json).

Design choices (all tunable via the rules files, none of them claimed as game formulas):
  * Outfield slot score = position-weighted average of the six main stats (0-100 scale).
  * GK slot score = the keeper's OVR (the six outfield stats don't describe keepers).
  * Playing out of a player's eligible positions multiplies the score by a penalty.
  * A player's PlayStyles add a small bonus to the relevant main stat(s).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional

from . import rules as rules_mod
from .models import MAIN_STATS, Player


@dataclass
class PlayerState:
    """A lightweight, copyable snapshot used by the optimiser and upgrade planner.

    Upgrades are simulated by producing a MODIFIED PlayerState (see helpers at the
    bottom) and re-scoring - the database is never touched during optimisation.
    """
    id: int
    name: str
    ovr: float
    rank: int
    training_level: int
    stats: dict[str, float]
    positions: list[str]
    rankup_positions: list[str] = field(default_factory=list)
    playstyles: list[dict] = field(default_factory=list)
    growth: dict[str, float] = field(default_factory=dict)
    skill_points: int = 0

    def copy(self) -> "PlayerState":
        return replace(
            self,
            stats=dict(self.stats),
            positions=list(self.positions),
            rankup_positions=list(self.rankup_positions),
            playstyles=[dict(p) for p in self.playstyles],
            growth=dict(self.growth),
        )


def player_to_state(p: Player) -> PlayerState:
    growth_default = rules_mod.load("growth")["default_gain_per_level"]
    growth = dict(growth_default)
    if p.growth_override:
        growth.update({k: v for k, v in p.growth_override.items() if v is not None})
    return PlayerState(
        id=p.id,
        name=p.name,
        ovr=float(p.ovr),
        rank=int(p.rank),
        training_level=int(p.training_level),
        stats={s: float(getattr(p, s)) for s in MAIN_STATS},
        positions=list(p.positions or []),
        rankup_positions=list(p.rankup_positions or []),
        playstyles=list(p.playstyles or []),
        growth=growth,
        skill_points=int(p.skill_points or 0),
    )


def effective_stats(state: PlayerState) -> dict[str, float]:
    """Main stats after applying PlayStyle bonuses (training level is already baked
    into the entered stats)."""
    ps_rules = rules_mod.load("playstyles")
    styles = ps_rules.get("styles", {})
    plus_mult = ps_rules.get("plus_multiplier", 2.0)

    out = dict(state.stats)
    for ps in state.playstyles:
        name = ps.get("name")
        if name not in styles:
            continue
        mult = plus_mult if ps.get("plus") else 1.0
        for stat, bonus in styles[name].items():
            if stat in out:
                out[stat] += bonus * mult
    # No upper cap: ranks, training and skills can legitimately push a stat past 100.
    return {k: max(0.0, v) for k, v in out.items()}


def _normalised_weights(position: str) -> dict[str, float]:
    weights = rules_mod.load("stat_weights")["weights"]
    w = weights.get(position, weights["DEFAULT"])
    total = sum(w.get(s, 0.0) for s in MAIN_STATS) or 1.0
    return {s: w.get(s, 0.0) / total for s in MAIN_STATS}


def _is_gk(state: PlayerState) -> bool:
    return "GK" in state.positions


def _gk_rating(state: PlayerState) -> float:
    """A keeper's rating from their six GK stats (Diving/Handling/Kicking/Reflexes/
    Positioning/Physical, stored in the six stat columns). Falls back to OVR if the
    GK stats were never filled in."""
    if sum(state.stats.values()) < 1e-6:
        return state.ovr
    eff = effective_stats(state)
    w = _normalised_weights("GK")
    return sum(eff[s] * w[s] for s in MAIN_STATS)


def slot_score(state: PlayerState, position: str) -> float:
    """Score of this player in this slot, on a 0-100-ish scale."""
    pos_rules = rules_mod.load("positions")
    oop_penalty = pos_rules.get("out_of_position_penalty", 0.82)
    gk_penalty = pos_rules.get("gk_mismatch_penalty", 0.05)

    if position == "GK":
        # Keepers are scored from their GK stats; a non-keeper in goal is prohibited.
        return _gk_rating(state) if _is_gk(state) else state.ovr * gk_penalty

    # Outfield slot.
    if _is_gk(state) and len(state.positions) == 1:
        # A pure keeper stuck outfield: prohibitive.
        factor = gk_penalty
    elif position in state.positions:
        factor = 1.0
    else:
        factor = oop_penalty

    eff = effective_stats(state)
    w = _normalised_weights(position)
    base = sum(eff[s] * w[s] for s in MAIN_STATS)
    return base * factor


def best_position_score(state: PlayerState) -> tuple[str, float]:
    """The player's own best position and score, ignoring the rest of the squad.
    Used for the bench view and gap analysis."""
    candidates = state.positions or ["ST"]
    best_pos, best = candidates[0], -1.0
    for pos in candidates:
        sc = slot_score(state, pos)
        if sc > best:
            best_pos, best = pos, sc
    return best_pos, best


# --------------------------------------------------------------------------
# Upgrade simulation helpers - each returns a NEW PlayerState, or None if the
# upgrade is not possible (already maxed / no resources).
# --------------------------------------------------------------------------

def with_training_level(state: PlayerState, delta_levels: int = 1) -> Optional[PlayerState]:
    max_level = rules_mod.load("growth").get("max_training_level", 30)
    new_level = state.training_level + delta_levels
    if new_level > max_level or delta_levels <= 0:
        return None
    ns = state.copy()
    ns.training_level = new_level
    for s in MAIN_STATS:
        ns.stats[s] = ns.stats[s] + ns.growth.get(s, 0.0) * delta_levels
    return ns


def with_rankup(state: PlayerState) -> Optional[PlayerState]:
    ru = rules_mod.load("rankup")
    max_rank = ru.get("max_rank", 5)
    if state.rank >= max_rank:
        return None
    ns = state.copy()
    ovr_gain = ru.get("ovr_gain", [1] * max_rank)
    gain = ovr_gain[state.rank] if state.rank < len(ovr_gain) else 1
    ns.ovr += gain
    stat_bump = ru.get("stat_gain_per_rank", 0.0)
    for s in MAIN_STATS:
        ns.stats[s] += stat_bump
    ns.rank += 1
    # Ranking up can unlock new positions.
    for pos in ns.rankup_positions:
        if pos not in ns.positions:
            ns.positions.append(pos)
    ns.rankup_positions = []
    return ns


def skill_point_gain(ovr: float) -> float:
    """How much a single (normal) skill point raises a main stat, scaled by base OVR
    per the FC Mobile skill-point rules (higher-rated cards gain more)."""
    sk = rules_mod.load("skills")
    bands = sk.get("ovr_scaled_gain", {}).get("bands", [{"max_ovr": 200, "normal": 1}])
    for b in bands:
        if ovr <= b["max_ovr"]:
            return float(b["normal"])
    return float(bands[-1]["normal"])


def fully_ranked_up(state: PlayerState) -> PlayerState:
    """The player after every remaining rank up (to the max rank): OVR/stat gains applied
    and all rank-up position unlocks granted. Used by the 'Potential XI' view so you can
    see the ceiling and know what to push for."""
    ru = rules_mod.load("rankup")
    max_rank = ru.get("max_rank", 5)
    s = state
    guard = 0
    while s.rank < max_rank and guard < 20:
        nxt = with_rankup(s)
        if nxt is None:
            break
        s = nxt
        guard += 1
    return s


def with_skill_point(state: PlayerState, stat: str) -> Optional[PlayerState]:
    if state.skill_points <= 0 or stat not in MAIN_STATS:
        return None
    ns = state.copy()
    ns.stats[stat] += skill_point_gain(state.ovr)
    ns.skill_points -= 1
    return ns


def priority_stats(state: PlayerState) -> list[str]:
    """The order in which to invest skill points for this player: the stats their
    PlayStyles boost come first (most-boosted first), then the position's key stats
    (skills.json position_priority), then anything remaining."""
    ps_rules = rules_mod.load("playstyles")
    styles = ps_rules.get("styles", {})
    plus_mult = ps_rules.get("plus_multiplier", 2.0)

    boost = {s: 0.0 for s in MAIN_STATS}
    for ps in state.playstyles:
        d = styles.get(ps.get("name"))
        if not d:
            continue
        mult = plus_mult if ps.get("plus") else 1.0
        for stat, val in d.items():
            if stat in boost and isinstance(val, (int, float)):
                boost[stat] += val * mult
    ps_order = [s for s, _ in sorted(boost.items(), key=lambda kv: kv[1], reverse=True) if boost[s] > 0]

    pos = state.positions[0] if state.positions else "DEFAULT"
    prio_map = rules_mod.load("skills").get("position_priority", {})
    pos_order = prio_map.get(pos, prio_map.get("DEFAULT", MAIN_STATS))

    out: list[str] = []
    for s in [*ps_order, *pos_order, *MAIN_STATS]:
        if s in MAIN_STATS and s not in out:
            out.append(s)
    return out
