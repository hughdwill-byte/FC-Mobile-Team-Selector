"""Refresh the player-card event backgrounds from the s8nag nag-screen archive.

The website themes each player card with the key art of its promo/season (TOTY, TOTS,
Ragnarok, ...). Those backgrounds live in  docs/img/events/<key>.jpg . This script rebuilds
them from a local checkout of the s8nag archive (https://github.com/Sappurit/s8nag), so when
new events are added there you just re-run this and the site picks up the latest art.

For each theme it scans the archive's filenames, matches by keyword, and keeps the NEWEST
image (highest-resolution variant), downscaled to a small web-friendly size. It also writes
docs/data/events.json (which key came from which dated event) for reference.

Typical flow:

    # one-time: clone the archive somewhere
    git clone https://github.com/Sappurit/s8nag ../s8nag

    python tools/build_event_art.py ../s8nag/img          # rebuild backgrounds
    python tools/build_event_art.py ../s8nag/img --push    # rebuild AND git commit + push

Adding a brand-new promo TYPE also needs one line in docs/js/cards-render.js (the variant
code -> theme mapping) and one KEYWORD entry below. Recurring promos (a new TOTY/TOTS each
year) refresh automatically to their latest art with no code change.

Needs: Pillow  (pip install Pillow)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "img" / "events"
MANIFEST = ROOT / "docs" / "data" / "events.json"
TARGET_W = 900
JPEG_QUALITY = 78

# theme key -> list of keyword phrases (lower-case) to look for in the event filename.
# Order matters: the FIRST key whose keyword matches wins, so put specific promos before generic
# ones (e.g. "uefa dreamchasers" before a bare "uefa"/"ucl").
KEYWORDS = [
    ("dreamchasers",  ["dreamchasers"]),
    ("halloflegends", ["hall of legends"]),
    ("cappedlegends", ["capped legends"]),
    ("gloriouseras",  ["glorious eras"]),
    ("ballondor",     ["ballon"]),
    ("trickortreat",  ["trick or treat", "scream team"]),
    ("worldcup",      ["world cup"]),
    ("twg",           ["the world's game", "worlds game", "world's game"]),
    ("footyverse",    ["footyverse"]),
    ("ragnarok",      ["ragnarok"]),
    ("neon",          ["neon"]),
    ("laliga",        ["laliga"]),
    ("captains",      ["captains"]),
    ("centurions",    ["centurions"]),
    ("heroes",        ["heroes"]),
    ("flashback",     ["flashback"]),
    ("carniball",     ["carniball", "carnival"]),
    ("festive",       ["festive", "football freeze"]),
    ("winter",        ["winter wonders", "winter wildcard", "winter"]),
    ("retro",         ["retro"]),
    ("mls",           ["mls"]),
    ("euro",          ["euro"]),
    ("aquainferno",   ["aqua vs inferno", "aqua", "inferno"]),
    ("champions",     ["champions"]),
    ("toty",          ["toty"]),
    ("tots",          ["tots"]),
    ("ucl",           ["ucl", "uecl", "ucl ", "champions league"]),
    ("anniversary",   ["anniversary"]),
]

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
RES_RE = re.compile(r"\((\d{3,4})\)")


def match_key(fname_lower: str):
    for key, phrases in KEYWORDS:
        for ph in phrases:
            if ph in fname_lower:
                return key
    return None


def build(src: Path) -> dict:
    if not src.exists():
        print(f"s8nag image folder not found: {src}\n"
              f"Clone it first:  git clone https://github.com/Sappurit/s8nag  then pass  <path>/img")
        sys.exit(1)

    # pick best (newest date, then highest resolution) source file per theme
    best: dict[str, tuple] = {}   # key -> (date, res, path)
    for p in sorted(src.iterdir()):
        if p.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        low = p.name.lower()
        key = match_key(low)
        if not key:
            continue
        dm = DATE_RE.search(p.name)
        date = dm.group(1) if dm else "0000-00-00"
        rm = RES_RE.search(p.name)
        res = int(rm.group(1)) if rm else 0
        cur = best.get(key)
        if cur is None or (date, res) > (cur[0], cur[1]):
            best[key] = (date, res, p)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    events = {}
    total = 0
    for key, (date, res, path) in sorted(best.items()):
        im = Image.open(path).convert("RGB")
        w, h = im.size
        nh = max(1, round(h * TARGET_W / w))
        im = im.resize((TARGET_W, nh), Image.LANCZOS)
        dst = OUT_DIR / f"{key}.jpg"
        im.save(dst, "JPEG", quality=JPEG_QUALITY, optimize=True)
        sz = dst.stat().st_size
        total += sz
        events[key] = {"date": date, "source": path.name}
        print(f"{key:14s} <- {date}  {path.name}  ({sz // 1024} KB)")

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({
        "updated": time.strftime("%Y-%m-%d"),
        "count": len(events),
        "source": "Backgrounds are EA SPORTS FC Mobile event key art, via the s8nag archive (github.com/Sappurit/s8nag).",
        "events": events,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {len(events)} backgrounds ({total // 1024} KB) + {MANIFEST.relative_to(ROOT)}")
    return events


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    push = "--push" in sys.argv
    if args:
        src = Path(args[0])
    else:
        # try a couple of common locations for a sibling checkout
        for cand in [ROOT.parent / "s8nag" / "img", ROOT / "s8nag" / "img", Path("/workspace/sappurit/s8nag/img")]:
            if cand.exists():
                src = cand
                break
        else:
            print("Pass the path to the s8nag image folder, e.g.:\n"
                  "  python tools/build_event_art.py ../s8nag/img")
            sys.exit(1)
    build(src)

    if push:
        try:
            subprocess.run(["git", "add", str(OUT_DIR), str(MANIFEST)], cwd=ROOT, check=True)
            subprocess.run(["git", "commit", "-m", "Update event card backgrounds"], cwd=ROOT, check=True)
            subprocess.run(["git", "push"], cwd=ROOT, check=True)
            print("Pushed - the live site will update in ~1 minute.")
        except subprocess.CalledProcessError as e:
            print(f"git step failed: {e}. (Nothing to commit? or run git push manually.)")


if __name__ == "__main__":
    main()
