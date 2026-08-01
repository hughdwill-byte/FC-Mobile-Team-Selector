"""Optimiser tests: build a squad whose best XI is obvious by hand."""
from backend.optimizer import optimize, best_squad_score
from backend.scoring import slot_score
from tests.test_scoring import mk


def _squad_433():
    """Exactly the 11 natural positions of a 4-3-3, each player eligible for one slot."""
    specs = [
        ("GK1", ["GK"], 86),
        ("RB1", ["RB"], 80),
        ("CB1", ["CB"], 84),
        ("CB2", ["CB"], 83),
        ("LB1", ["LB"], 79),
        ("CM1", ["CM"], 82),
        ("CM2", ["CM"], 81),
        ("CM3", ["CM"], 80),
        ("RW1", ["RW"], 85),
        ("ST1", ["ST"], 88),
        ("LW1", ["LW"], 84),
    ]
    players = []
    for i, (name, pos, ovr) in enumerate(specs):
        # give each a slightly different stat spread so scores are distinct
        players.append(mk(id=i + 1, name=name, positions=pos, ovr=ovr, stats=70 + i))
    return players


def test_best_formation_matches_natural_positions():
    players = _squad_433()
    results = optimize(players, top_n=5)
    best = results[0]
    assert best.formation == "4-3-3"

    # Every player lands in their natural slot, and the total is the hand-sum.
    by_name = {a.player_name: a for a in best.slots}
    manual_total = 0.0
    for p in players:
        pos = p.positions[0]
        # find the slot this player was assigned to
        assigned = by_name[p.name]
        assert assigned.position == pos
        manual_total += slot_score(p, pos)
    assert abs(best.total - manual_total) < 1e-6


def test_results_sorted_descending():
    results = optimize(_squad_433(), top_n=5)
    totals = [r.total for r in results]
    assert totals == sorted(totals, reverse=True)


def test_optimizer_picks_the_better_of_two_strikers():
    players = _squad_433()
    # Add a clearly superior backup striker; the optimiser must start them over ST1.
    strong = mk(id=99, name="SuperST", positions=["ST"], ovr=99, stats=99)
    players.append(strong)
    best = optimize(players, top_n=1)[0]
    # SuperST must be in the starting XI at a striker slot.
    st_names = [a.player_name for a in best.slots if a.position == "ST"]
    assert "SuperST" in st_names


def test_runner_up_is_reported():
    best = optimize(_squad_433(), top_n=1)[0]
    for a in best.slots:
        # With 11 players for 11 slots there is no spare, so runner-up may be None,
        # but the field must exist and be consistent.
        assert hasattr(a, "runner_up_name")


def test_fewer_than_eleven_leaves_empty_slots():
    players = _squad_433()[:9]
    best = optimize(players, top_n=1)[0]
    empties = [a for a in best.slots if a.player_id is None]
    assert len(empties) == 2


def test_fully_ranked_up_never_lowers_squad_score():
    from backend.scoring import fully_ranked_up
    players = _squad_433()
    for p in players:
        p.rank = 1
    current = optimize(players, top_n=1)[0].total
    potential = optimize([fully_ranked_up(p) for p in players], top_n=1)[0].total
    assert potential >= current
