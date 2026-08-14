"""Build the card database the website uses, from your RenderZ spreadsheet.

Turns  renderz_players_24.xlsx  ->  docs/data/cards.json  (lean, no images),
pre-mapped to the app's six-stat model so the site can auto-fill a player card.

Typical flow after you've refreshed your spreadsheet with your own scraper:

    python tools/build_cards.py                 # rebuild docs/data/cards.json
    python tools/build_cards.py --push          # rebuild AND git commit + push

    python tools/build_cards.py path/to/file.xlsx --push   # explicit spreadsheet

So instead of manually replacing a file on GitHub each time, you run one command
and the live site updates. Only the compact JSON is committed (not the xlsx, not
any card art) - stats only.

Needs: openpyxl  (pip install openpyxl)
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data" / "cards.json"
SKILL_FX = ROOT / "docs" / "data" / "skill_effects.json"
MAIN6 = ["PAC", "SHO", "PAS", "DRI", "DEF", "PHY"]


def load_skill_fx():
    try:
        return json.loads(SKILL_FX.read_text(encoding="utf-8"))
    except Exception:
        return None


def _skill_head_delta(entry, weights):
    """One skill's effect on the six headline stats (flat sub-attribute boosts folded via weights)."""
    amt = entry["l2"] if entry.get("l2") is not None else entry.get("l1")
    if amt is None:
        return None
    boosts = {}
    for s in entry["subs"]:
        boosts[s] = boosts.get(s, 0) + amt
    return [round(sum(weights.get(head, {}).get(s, 0) * b for s, b in boosts.items())) for head in MAIN6]


def forced_skill_deltas(path_str, fx):
    """Ordered list of the FORCED (non-caps) skills' six-stat deltas, in path order. Skills are applied in
    order as a card ranks up (one per rank), forced ones first, so the engine applies the first `rank` of
    these. ALL-CAPS entries are the player's manual choice and are excluded. Returns a list of [6] or None."""
    if not path_str or not fx:
        return None
    skills, aliases, weights = fx["skills"], fx.get("aliases", {}), fx["weights"]
    out = []
    for part in str(path_str).split(">"):
        p = part.strip()
        if not p or p.isupper():           # blank or ALL-CAPS player choice
            continue
        entry = skills.get(aliases.get(p, p))
        if not entry:
            continue
        d = _skill_head_delta(entry, weights)
        if d:
            out.append(d)
    return out or None

# The app's six stat columns, in order: pace, shooting, passing, dribbling, defending, physical.
OUTFIELD = ["PAC", "SHO", "PAS", "DRI", "DEF", "PHY"]
# Goalkeepers map their GK stats onto the same six slots.
GK = ["DIV", "HAN", "KIC", "REF", "POS", "PHY"]  # -> pace,shooting,passing,dribbling,defending,physical


def prettify_variant(v):
    if not v:
        return ""
    return str(v).replace("_", " ").strip()


import re


def _split_pos(raw):
    out = []
    if raw:
        for p in str(raw).replace("/", ",").split(","):
            p = p.strip().upper()
            if p and p not in out:
                out.append(p)
    return out


def main_positions(row):
    # X (position_detail) is the position(s) the card plays now; fall back to the plain column.
    return _split_pos(row.get("position_detail") or row.get("position"))


def rankup_positions(row, main):
    # Y (alt_positions_detail) are alternates that unlock after ranking the card up; keep them separate.
    return [p for p in _split_pos(row.get("alt_positions_detail") or row.get("alt_positions")) if p not in main]


def playstyles(row):
    # AJ looks like "Rapid (Level 2) | Clinical Finisher (Level 1)". Keep raw name + level; the app maps
    # names and treats Level 2 as the gold (PlayStyle+) version.
    raw = row.get("playstyles")
    if not raw:
        return []
    out = []
    for part in str(raw).split("|"):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"(.+?)\s*\(Level\s*(\d)\)\s*$", part)
        if m:
            out.append([m.group(1).strip(), int(m.group(2))])
        else:
            out.append([part, 1])
    return out


def num(v):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return 0


def build(xlsx: Path) -> dict:
    wb = openpyxl.load_workbook(xlsx, read_only=True)
    ws = wb.active
    it = ws.iter_rows(values_only=True)
    header = list(next(it))
    fx = load_skill_fx()
    cards = []
    for r in it:
        row = dict(zip(header, r))
        name = row.get("name")
        if not name:
            continue
        main = main_positions(row)
        is_gk = "GK" in main or str(row.get("position") or "").upper() == "GK"
        cols = GK if is_gk else OUTFIELD
        stats = [num(row.get(c)) for c in cols]
        card = {
            "id": str(row.get("card_id")),
            "n": str(name),
            "o": num(row.get("overall")),
            "p": main,
            "gk": 1 if is_gk else 0,
            "s": stats,
            "v": prettify_variant(row.get("variant")),
        }
        ru = rankup_positions(row, main)
        if ru:
            card["ru"] = ru               # alt positions that unlock on rank up
        ps = playstyles(row)
        if ps:
            card["ps"] = ps               # [[name, level], ...]
        if not is_gk:                     # skill deltas: outfield only (GK formula differs)
            fsd = forced_skill_deltas(row.get("skill_boost_path"), fx)
            if fsd:
                card["fsd"] = fsd         # ordered forced-skill six-stat deltas (apply first `rank`)
        cards.append(card)
    # newest/highest first is nice for ties; keep sheet order otherwise
    return {
        "season": xlsx.stem.split("_")[-1] if "_" in xlsx.stem else "",
        "count": len(cards),
        "updated": time.strftime("%Y-%m-%d"),
        "source": "Compiled from RenderZ (renderz.app) - stats only, no card art.",
        "cards": cards,
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    push = "--push" in sys.argv
    xlsx = Path(args[0]) if args else (ROOT / "renderz_players_24.xlsx")
    if not xlsx.exists():
        print(f"Spreadsheet not found: {xlsx}\nPass the path: python tools/build_cards.py <file.xlsx>")
        sys.exit(1)

    data = build(xlsx)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    kb = OUT.stat().st_size / 1024
    print(f"Wrote {data['count']} cards -> {OUT.relative_to(ROOT)}  ({kb:.0f} KB)")

    if push:
        try:
            subprocess.run(["git", "add", str(OUT)], cwd=ROOT, check=True)
            subprocess.run(["git", "commit", "-m", f"Update card database ({data['count']} cards)"], cwd=ROOT, check=True)
            subprocess.run(["git", "push"], cwd=ROOT, check=True)
            print("Pushed to GitHub - the live site will update in ~1 minute.")
        except subprocess.CalledProcessError as e:
            print(f"git step failed: {e}. (Nothing to commit? or run git push manually.)")


if __name__ == "__main__":
    main()
