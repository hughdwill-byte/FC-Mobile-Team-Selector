"""Load a small sample squad so you can try the app before entering your own players.

    python seed_sample.py            # add sample players (keeps existing ones)
    python seed_sample.py --replace  # wipe the DB first, then add samples

Delete these later from the Players screen, or just start with an empty DB by not
running this at all.
"""
from __future__ import annotations

import sys

from backend import db
from backend.db import init_db
from backend.models import Player

SAMPLE = [
    # name, ovr, rank, lvl, pace, sho, pas, dri, def, phy, positions, playstyles
    ("Aria Fox",      88, 2, 12, 92, 90, 78, 89, 34, 74, ["ST", "CF"], [("Rapid", True), ("Clinical Finisher", False)]),
    ("Kofi Mensah",   86, 1,  8, 90, 84, 74, 88, 30, 70, ["ST"],        [("Finesse Expert", False)]),
    ("Luca Ferrari",  85, 3, 15, 82, 62, 88, 86, 40, 66, ["CAM", "CM"], [("Bullet Pass", True)]),
    ("Diego Santos",  84, 1,  6, 88, 55, 80, 85, 48, 62, ["RW", "RM"],  [("Technical", False)]),
    ("Yuki Tanaka",   83, 2, 10, 89, 52, 78, 84, 45, 60, ["LW", "LM"],  [("Trickster", False)]),
    ("Omar Haddad",   85, 2, 11, 70, 60, 84, 80, 82, 78, ["CDM", "CM"], [("Anticipate", True)]),
    ("Ben Carter",    84, 1,  7, 72, 45, 80, 76, 80, 80, ["CM", "CDM"], [("Guardian", False)]),
    ("Marco Rossi",   86, 3, 14, 74, 40, 70, 66, 88, 86, ["CB"],        [("Bruiser", True)]),
    ("Sven Johansson",85, 2,  9, 76, 38, 68, 64, 87, 85, ["CB"],        [("Anticipate", False)]),
    ("Paulo Alves",   83, 1,  5, 84, 42, 76, 74, 78, 72, ["RB", "RWB"], [("Bruiser", False)]),
    ("Tom Wright",    82, 1,  4, 85, 40, 74, 73, 77, 70, ["LB", "LWB"], []),
    # GK: the six columns are Diving, Handling, Kicking, Reflexes, Positioning, Physical
    ("Ivan Petrov",   87, 0,  0, 85, 84, 70, 88, 83, 82, ["GK"],        [("Rush Out", False)]),
    # bench-ish depth
    ("Noah Kim",      80, 0,  3, 86, 78, 68, 82, 28, 64, ["ST"],        []),
    ("Ali Reza",      81, 1,  6, 68, 50, 82, 78, 76, 70, ["CM"],        [("Tiki Taka", False)]),
    ("Jack Moss",     79, 0,  2, 70, 36, 66, 62, 82, 80, ["CB"],        []),
    ("Leo Duarte",    80, 1,  5, 82, 44, 74, 72, 74, 68, ["LB"],        []),
    ("Sam Pryce",     78, 0,  1, 80, 40, 70, 76, 40, 60, ["RW", "LW"],  []),
]


def main() -> None:
    replace = "--replace" in sys.argv
    init_db()
    if replace:
        db.delete_all()
    for (name, ovr, rank, lvl, pac, sho, pas, dri, dfn, phy, pos, styles) in SAMPLE:
        db.create(Player(
            name=name, ovr=ovr, rank=rank, training_level=lvl,
            pace=pac, shooting=sho, passing=pas, dribbling=dri, defending=dfn, physical=phy,
            positions=pos,
            playstyles=[{"name": n, "plus": plus} for (n, plus) in styles],
        ))
    print(f"Seeded {len(SAMPLE)} sample players (replace={replace}).")


if __name__ == "__main__":
    main()
