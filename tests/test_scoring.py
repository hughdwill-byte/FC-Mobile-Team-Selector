"""Scoring tests with tiny, hand-checkable inputs."""
import math

from backend.scoring import (
    PlayerState,
    effective_stats,
    slot_score,
    with_rankup,
    with_skill_point,
    with_training_level,
)


def mk(stats=80, positions=("ST",), **kw):
    base = {s: float(stats) for s in ["pace", "shooting", "passing", "dribbling", "defending", "physical"]}
    base.update({k: v for k, v in kw.items() if k in base})
    return PlayerState(
        id=kw.get("id", 1),
        name=kw.get("name", "P"),
        ovr=kw.get("ovr", 80),
        rank=kw.get("rank", 0),
        training_level=kw.get("training_level", 0),
        stats=base,
        positions=list(positions),
        playstyles=kw.get("playstyles", []),
        growth=kw.get("growth", {s: 1.0 for s in base}),
        skill_points=kw.get("skill_points", 0),
    )


def test_out_of_position_penalty_is_applied():
    natural = mk(positions=["CM"])
    out = mk(positions=["ST"])  # identical stats, wrong position for a CM slot
    s_natural = slot_score(natural, "CM")
    s_out = slot_score(out, "CM")
    # Same stats + same CM weights, so the only difference is the OOP penalty (0.82).
    assert s_out < s_natural
    assert math.isclose(s_out / s_natural, 0.82, rel_tol=1e-6)


def test_gk_scoring_uses_gk_stats_and_blocks_outfielders():
    keeper = mk(positions=["GK"], ovr=87)          # all six GK stats = 80
    striker = mk(positions=["ST"], ovr=87)
    # Keeper is scored from their GK stats (~80), not from OVR.
    assert 70 < slot_score(keeper, "GK") < 90
    # A keeper with no GK stats entered falls back to OVR.
    blank = mk(positions=["GK"], ovr=87, stats=0)
    assert math.isclose(slot_score(blank, "GK"), 87.0)
    # A non-keeper in goal is effectively prohibited (tiny score).
    assert slot_score(striker, "GK") < 10


def test_priority_stats_puts_playstyle_and_position_first():
    from backend.scoring import priority_stats
    # A CB with a Bruiser (physical) PlayStyle: physical should lead, defending high too.
    cb = mk(positions=["CB"], playstyles=[{"name": "Bruiser", "plus": False}])
    order = priority_stats(cb)
    assert order[0] == "physical"          # PlayStyle-boosted stat first
    assert order.index("defending") < order.index("shooting")  # position priority beats irrelevant stat
    assert set(order) == set(["pace", "shooting", "passing", "dribbling", "defending", "physical"])


def test_playstyle_adds_bonus():
    plain = mk(positions=["ST"])
    boosted = mk(positions=["ST"], playstyles=[{"name": "Rapid", "plus": True}])
    assert effective_stats(boosted)["pace"] > effective_stats(plain)["pace"]
    assert slot_score(boosted, "ST") > slot_score(plain, "ST")


def test_training_raises_stats_and_respects_cap():
    p = mk(training_level=10, growth={s: 0.5 for s in
           ["pace", "shooting", "passing", "dribbling", "defending", "physical"]})
    up = with_training_level(p, 1)
    assert up.training_level == 11
    assert math.isclose(up.stats["pace"], p.stats["pace"] + 0.5)
    maxed = mk(training_level=30)
    assert with_training_level(maxed, 1) is None


def test_rankup_increases_ovr_and_unlocks_positions():
    p = mk(positions=["ST"], rank=1, ovr=80)
    p.rankup_positions = ["CF"]
    up = with_rankup(p)
    assert up.rank == 2
    assert up.ovr > p.ovr
    assert "CF" in up.positions
    maxed = mk(rank=5)
    assert with_rankup(maxed) is None


def test_skill_point_spend():
    p = mk(positions=["ST"], skill_points=1)
    up = with_skill_point(p, "shooting")
    assert up.skill_points == 0
    assert up.stats["shooting"] > p.stats["shooting"]
    assert with_skill_point(mk(skill_points=0), "shooting") is None
