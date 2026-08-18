"""
RenderZ incremental UPDATE  ->  the website's card database
===========================================================

Scrapes the newest cards from RenderZ, appends them (with full details) to the
working spreadsheet, and then rebuilds the site's  docs/data/cards.json  so the
change goes straight into the page - instead of only saving a file on your
computer. Nothing else to do: the site reads cards.json directly.

It crawls  https://renderz.app/<season>/players?sortType=added  (newest first)
and stops once it runs into cards already in the sheet (matched by card_id),
then re-runs the same builder the site uses (tools/build_cards.py).

RUN LOCALLY:
    python tools/renderz_update.py                 # update sheet + rebuild cards.json
    python tools/renderz_update.py <file.xlsx>      # explicit spreadsheet
    python tools/renderz_update.py <file.xlsx> 24   # spreadsheet + season

RUN AUTOMATICALLY:
    .github/workflows/update-cards.yml runs this every day and commits the
    refreshed docs/data/cards.json back to the repo (see that file).

Needs, alongside this script:  renderz_scraper.py  and  renderz_details.py
(your scraper modules), plus:   pip install pandas openpyxl beautifulsoup4
"""

import sys
import json
import asyncio
import pathlib

import pandas as pd
import renderz_scraper as rs
import renderz_details as rd

# tools/ is on sys.path when run as "python tools/renderz_update.py"; make the sibling builder importable
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_cards  # the exact builder the website uses (xlsx -> lean cards.json)

ROOT = pathlib.Path(__file__).resolve().parent.parent
CARDS_JSON = ROOT / "docs" / "data" / "cards.json"

# The working spreadsheet lives in the repo so incremental updates persist between runs. Prefer the
# DETAILED sheet (attr_* / skill paths / alt positions / playstyles) so the site keeps skills, rank-up
# positions and playstyles; fall back to the basic one only if that's all that's there.
def _find_xlsx():
    for name in (f"renderz_full_{rs.SEASON}.xlsx", f"renderz_players_{rs.SEASON}.xlsx"):
        p = ROOT / name
        if p.exists():
            return p
    return ROOT / f"renderz_full_{rs.SEASON}.xlsx"

XLSX = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else _find_xlsx()
SEASON = sys.argv[2] if len(sys.argv) > 2 else rs.SEASON

UPDATE_STATS_MODE = "both"   # capture new outfield (Player stats) AND new GKs (GK stats)
HEADLESS = True              # run both stages invisibly


def rebuild_site_cards():
    """Regenerate docs/data/cards.json from the (updated) spreadsheet, using the site's own builder."""
    data = build_cards.build(XLSX)
    CARDS_JSON.parent.mkdir(parents=True, exist_ok=True)
    CARDS_JSON.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    kb = CARDS_JSON.stat().st_size / 1024
    print(f"Rebuilt page cards -> {CARDS_JSON.relative_to(ROOT)}  ({data['count']} cards, {kb:.0f} KB)")


def main():
    if not XLSX.exists():
        print(f"Can't find {XLSX}. Commit your detailed sheet (renderz_full_{SEASON}.xlsx) to the repo, "
              "or pass its path.")
        return

    rs.HEADLESS = HEADLESS
    rd.HEADLESS = HEADLESS

    existing = pd.read_excel(XLSX)
    existing["card_id"] = existing["card_id"].astype(str)
    known = set(existing["card_id"])
    has_details = any(str(c).startswith("attr_") for c in existing.columns)
    print(f"Existing: {XLSX.name}  ({len(existing)} rows, {len(known)} card ids, "
          f"details={'yes' if has_details else 'no'})")
    if not has_details:
        print("  NOTE: this sheet has no detail columns, so the rebuilt cards.json will lack skills / "
              "rank-up positions / playstyles. Use the detailed renderz_full sheet to keep those.")

    # 1) scrape the newest list, stopping when we hit known cards
    print(f"Checking for new cards (season {SEASON}, stats={UPDATE_STATS_MODE})...")
    list_result = rs.scrape(sort="added", band=None, stats_mode=UPDATE_STATS_MODE,
                            known_ids=known, season=SEASON)

    added = 0
    if list_result:
        new_base = rs.to_dataframe(list_result)
        new_base["card_id"] = new_base["card_id"].astype(str)
        new_base = new_base[~new_base["card_id"].isin(known)]
        if not new_base.empty:
            new_ids = list(dict.fromkeys(new_base["card_id"].tolist()))
            print(f"{len(new_ids)} new card(s) found.")

            # 2) if the sheet has detail columns, fetch full details for the new cards
            new_full = new_base
            if has_details:
                print(f"Fetching detail pages for the {len(new_ids)} new card(s)...")
                rd.results.clear()
                asyncio.run(rd.enrich_cards(new_ids, dump_sample=False))
                det = pd.DataFrame([rd.results[i] for i in new_ids if i in rd.results])
                if not det.empty:
                    det = det.drop(columns=[c for c in ["_has_attrs"] if c in det.columns])
                    det["card_id"] = det["card_id"].astype(str)
                    new_full = new_base.merge(det, on="card_id", how="left", suffixes=("", "_detail"))

            # 3) append and save the spreadsheet (the persistent working store)
            merged = pd.concat([existing, new_full], ignore_index=True)
            merged = merged.drop_duplicates(subset=["card_id"], keep="first")
            merged.to_excel(XLSX, index=False)
            added = len(new_full)
            print(f"Added {added} new card(s) to {XLSX.name}. Total now {len(merged)}.")
            for _, r in new_full.head(25).iterrows():
                print(f"  {str(r.get('name'))[:20]:20} OVR {r.get('overall')} {r.get('position')}")
            if added > 25:
                print(f"  ... and {added - 25} more")
        else:
            print("No new cards after filtering.")
    else:
        print("No new cards found.")

    # 4) ALWAYS rebuild the page's cards.json from the current sheet (so a re-run also picks up any
    #    fixes to the builder, and the site always matches the spreadsheet).
    rebuild_site_cards()
    if not added:
        print("(no new cards, but cards.json was refreshed from the sheet)")


if __name__ == "__main__":
    main()
