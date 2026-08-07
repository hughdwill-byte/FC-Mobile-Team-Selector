"""Takeover-planner tests."""
from backend.targets import compute_takeover
from tests.test_scoring import mk

STATS = ["pace", "shooting", "passing", "dribbling", "defending", "physical"]


def test_transfer_takes_incumbent_level_minus_fee():
    incumbent = mk(positions=["ST"], ovr=80, training_level=20, stats=80)
    target = mk(positions=["ST"], ovr=80, training_level=0, stats=60,
                growth={s: 1.0 for s in STATS})
    r = compute_takeover(target, incumbent, "ST")
    assert r["transfer_levels"] == 18          # floor(20 * 0.9)
    assert r["achievable"] is True
    assert r["final_level"] >= 18


def test_rankup_needed_to_unlock_position():
    incumbent = mk(positions=["ST"], ovr=80, training_level=0, stats=70)
    target = mk(positions=["CM"], ovr=85, training_level=0, stats=80)
    target.rankup_positions = ["ST"]
    r = compute_takeover(target, incumbent, "ST")
    assert r["rankups"]                        # at least one rank up to unlock ST
    assert r["achievable"] is True


def test_unreachable_when_incumbent_far_better():
    incumbent = mk(positions=["ST"], ovr=99, training_level=30, stats=99)
    target = mk(positions=["ST"], ovr=60, training_level=0, stats=50,
                growth={s: 0.4 for s in STATS})
    r = compute_takeover(target, incumbent, "ST")
    assert r["achievable"] is False            # even fully maxed, can't reach
