"""Upgrade-planner tests."""
from backend.upgrades import plan_upgrades
from tests.test_optimizer import _squad_433
from tests.test_scoring import mk


def test_plan_has_structure_and_positive_gains():
    players = []
    for i, p in enumerate(_squad_433()):
        p.training_level = 10
        p.rank = 1
        players.append(p)
    plan = plan_upgrades(players)
    assert "baseline_squad_score" in plan
    assert plan["combined"], "expected some improving upgrades"
    for c in plan["combined"]:
        assert c["gain"] > 0
        assert c["combined_cost"] > 0
        assert {"kind", "player_name", "gain_per_cost"} <= set(c)


def test_maxed_squad_offers_no_upgrades():
    players = []
    for p in _squad_433():
        p.training_level = 30
        p.rank = 5
        p.skill_points = 0
        players.append(p)
    plan = plan_upgrades(players)
    assert plan["combined"] == []


def test_upgrading_a_benched_player_can_flip_them_into_the_xi():
    players = _squad_433()  # CB starters have stat spreads 72 and 73
    bench_cb = mk(id=50, name="BenchCB", positions=["CB"], ovr=82, stats=71,
                  training_level=10,
                  growth={s: 5.0 for s in
                          ["pace", "shooting", "passing", "dribbling", "defending", "physical"]})
    players.append(bench_cb)
    plan = plan_upgrades(players)
    flips = [c for c in plan["combined"]
             if c["player_name"] == "BenchCB" and c["kind"] == "training"]
    assert flips and flips[0]["gain"] > 0
