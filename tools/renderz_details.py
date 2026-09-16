"""
RenderZ DETAIL enrichment  (v3: names from the server HTML, attributes from render)
==================================================================================

Adds full player-page data to your spreadsheet: every sub-attribute (Acceleration,
Sprint Speed, Finishing ...), playstyles + levels, traits / skill move /
celebration, skill-boost path, and full bio (team, league, nation, foot, height,
weight, work rates, added date, full name, card image).

How it gets real NAMES: the player page's raw server HTML already contains the
translated names (France, Icons, Trickster ...). The site's JavaScript later
swaps them back to codes like "NationName_133", which is why an on-page read
showed codes. So this reads the text fields from the server response, and uses
the rendered page only for the attribute grid (which is JS-rendered).

Reliability: retries errored/attribute-less cards, resumes from a cache, reports
anything still incomplete. Goalkeepers automatically show keeper attributes.

SETUP:  pip install playwright pandas openpyxl beautifulsoup4
        playwright install chromium
RUN:    python renderz_details.py
        python renderz_details.py renderz_players_24.xlsx
"""

import sys
import re
import json
import asyncio
import pathlib

import pandas as pd
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import renderz_scraper as rs

XLSX = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else rs.OUT_XLSX
SEASON = rs.SEASON

CONCURRENCY = 8           # parallel player pages (4-8 sensible)
MAX_CARDS = None          # None = all; keep small for the first test
BAND = None               # e.g. (100, 122) to enrich only that range; None = all
MAX_RETRIES = 3           # extra rounds to retry errored / attribute-less cards
CHECKPOINT_EVERY = 100
HEADLESS = True           # can stay headless now (names come from server HTML)

OUT = XLSX.with_name(XLSX.stem + "_detailed.xlsx")
CACHE = pathlib.Path(f"renderz_details_cache_{SEASON}.json")
SAMPLE = pathlib.Path("detail_sample.html")

SUB_ATTRS = ["Acceleration", "Sprint Speed", "Finishing", "Long Shot", "Long Shots",
             "Shot Power", "Positioning", "Volley", "Volleys", "Penalties",
             "Short Passing", "Long Passing", "Vision", "Crossing", "Curve",
             "Free Kick", "Free Kick Accuracy", "Dribbling", "Balance", "Agility",
             "Reactions", "Ball Control", "Marking", "Standing Tackle",
             "Sliding Tackle", "Awareness", "Interceptions", "Heading",
             "Heading Accuracy", "Strength", "Aggression", "Jumping", "Stamina",
             "Diving", "Handling", "Kicking", "Reflexes", "Speed"]

# attribute grid is JS-rendered -> read it from the live DOM
ATTR_JS = r"""
(SUB) => {
  const leaves = Array.from(document.querySelectorAll('span,div,p,td'))
    .filter(e => e.children.length === 0);
  const exact = (l) => leaves.filter(e => e.textContent.trim() === l);
  const nn = (el) => {
    let p = el;
    for (let i = 0; i < 4 && p; i++) {
      p = p.parentElement; if (!p) break;
      const nums = Array.from(p.querySelectorAll('*'))
        .filter(n => n !== el && n.children.length === 0 && /^\d{1,3}$/.test(n.textContent.trim()));
      if (nums.length) return nums[0].textContent.trim();
    }
    return null;
  };
  const a = {};
  for (const L of SUB) { if (L in a) continue; for (const el of exact(L)) { const v = nn(el); if (v !== null) { a[L] = v; break; } } }
  return a;
}
"""

results = {}


def parse_ssr(html):
    """Pull the translated text fields from the raw server HTML."""
    soup = BeautifulSoup(html, "html.parser")
    d = {}
    for lab in soup.find_all("span"):
        if "uppercase" in (lab.get("class") or []):
            label = lab.get_text(" ", strip=True)
            par = lab.parent
            val = ""
            if par:
                for sib in par.find_all("span"):
                    if "font-semibold" in (sib.get("class") or []):
                        val = sib.get_text(" ", strip=True)
                        break
            if label and val and label not in d:
                d[label] = val

    playstyles = []
    for sp in soup.find_all("span"):
        t = sp.get_text(strip=True)
        if re.fullmatch(r"Level \d+", t):
            prev = sp.find_previous_sibling("span")
            if prev:
                nm = prev.get_text(strip=True)
                if nm and not nm.startswith("PLAYSTYLE_"):
                    playstyles.append(f"{nm} ({t})")

    def names_for(frag):
        res = []
        for im in soup.find_all("img", src=True):
            if frag in im["src"]:
                for sp in im.find_all_next("span", limit=8):
                    nm = sp.get_text(strip=True)
                    if nm and len(nm) < 45:
                        res.append(nm)
                        break
        return res

    action = ""
    for im in soup.find_all("img", src=True):
        if "/player_" in im["src"]:
            action = im["src"]
            break
    title = soup.find("title")
    full_name = title.get_text().split("|")[0].strip() if title else ""
    foot = d.get("STRONG FOOT / WEAK FOOT", "")
    strong_foot = foot.split("/")[0].strip() if foot else ""
    wm = re.search(r"\((\d)\)", foot)
    sm = re.search(r"\((\d)\)", d.get("Skill Moves", ""))
    return {
        "full_name": full_name,
        "position_detail": d.get("Position", ""),
        "alt_positions_detail": d.get("Alternate Postions", d.get("Alternate Positions", "")),
        "team": d.get("TEAM", ""), "league": d.get("LEAGUE", ""),
        "nation": d.get("NATION/REGION", ""),
        "skill_moves": sm.group(1) if sm else d.get("Skill Moves", ""),
        "strong_foot": strong_foot, "weak_foot": wm.group(1) if wm else "",
        "height": d.get("Height", ""), "weight": d.get("Weight", ""),
        "work_rate": d.get("Work Rate (ATT) / Work Rate (DEF)", ""),
        "added_on": d.get("Added on", ""),
        "playstyles": " | ".join(playstyles),
        "traits": ", ".join(dict.fromkeys(names_for("/traitlogo_"))),
        "skill_move": (names_for("/skillmovelogo_") or [""])[0],
        "celebration": (names_for("/celebrationlogo_") or [""])[0],
        "skill_boost_path": " > ".join(names_for("/skill_S10_")),
        "card_image_url": action,
    }


def is_complete(row):
    return bool(row) and not row.get("error") and row.get("_has_attrs")


async def enrich_one(page, card_id, dump_sample=False):
    url = f"https://renderz.app/player/{card_id}"   # redesign dropped the /season/ segment; numeric id redirects
    resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    try:
        ssr_html = await resp.text() if resp else ""
    except Exception:
        ssr_html = ""
    try:
        await page.wait_for_function(
            "() => /Acceleration|Reflexes|Diving|Sprint Speed/.test(document.body.innerText)",
            timeout=15000)
    except Exception:
        pass
    attrs = await page.evaluate(ATTR_JS, SUB_ATTRS)
    if dump_sample:
        try:
            SAMPLE.write_text(ssr_html or await page.content(), encoding="utf-8")
            print(f"  saved {SAMPLE.resolve()}")
        except Exception:
            pass
    row = {"card_id": str(card_id)}
    row.update(parse_ssr(ssr_html) if ssr_html else {})
    for k, v in (attrs or {}).items():
        row[f"attr_{k}"] = v
    row["_has_attrs"] = bool(attrs)
    return row


async def route_handler(route):
    try:
        if rs.is_blocked(route.request.url):
            await route.abort()
        else:
            await route.continue_()
    except Exception:
        pass


first_flag = {"do": True}


async def worker(browser, queue):
    ctx = await browser.new_context(viewport={"width": 1400, "height": 1000},
                                    locale="en-GB")
    await ctx.route("**/*", route_handler)
    page = await ctx.new_page()
    while True:
        try:
            card_id = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        try:
            dump = first_flag["do"]
            if dump:
                first_flag["do"] = False
            row = await enrich_one(page, card_id, dump_sample=dump)
        except Exception as e:
            row = {"card_id": str(card_id), "error": str(e)[:80], "_has_attrs": False}
        results[str(card_id)] = row
        queue.task_done()
        if len(results) % 25 == 0:
            print(f"  ...{len(results)} processed")
        if len(results) % CHECKPOINT_EVERY == 0:
            save_cache()   # cache is the resume/safety mechanism (no xlsx here)
    await ctx.close()


def save_cache():
    try:
        CACHE.write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def save_xlsx():
    if not results:
        return
    det = pd.DataFrame(list(results.values()))
    det = det.drop(columns=[c for c in ["_has_attrs"] if c in det.columns])
    det["card_id"] = det["card_id"].astype(str)
    if XLSX.exists():
        base = pd.read_excel(XLSX)
        base["card_id"] = base["card_id"].astype(str)
        merged = base.merge(det, on="card_id", how="left", suffixes=("", "_detail"))
    else:
        print(f"(base sheet {XLSX.name} not found — writing details only)")
        merged = det
    merged.to_excel(OUT, index=False)
    print(f"\nSaved -> {OUT.resolve()}")


async def run_round(ids):
    queue = asyncio.Queue()
    for i in ids:
        queue.put_nowait(i)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        workers = [asyncio.create_task(worker(browser, queue)) for _ in range(CONCURRENCY)]
        await asyncio.gather(*workers)
        await browser.close()


async def enrich_cards(card_ids, dump_sample=True):
    """Enrich card_ids with detail data; resumes from CACHE, retries incompletes.
    Populates and returns the module `results` dict. Reusable by renderz_full.py."""
    if not dump_sample:
        first_flag["do"] = False
    if CACHE.exists():
        try:
            cached = json.loads(CACHE.read_text(encoding="utf-8"))
            results.update({k: v for k, v in cached.items() if is_complete(v)})
            print(f"Resuming: {len(results)} cards already complete in cache.")
        except Exception:
            pass
    ids = [str(i) for i in card_ids]
    todo = [i for i in ids if not is_complete(results.get(i))]
    print(f"Enriching {len(todo)} of {len(ids)} cards (concurrency {CONCURRENCY})...")
    for attempt in range(MAX_RETRIES + 1):
        if not todo:
            break
        if attempt:
            print(f"Retry round {attempt}: {len(todo)} incomplete card(s)...")
        await run_round(todo)
        save_cache()
        todo = [i for i in ids if not is_complete(results.get(i))]
    save_cache()
    incomplete = [i for i in ids if not is_complete(results.get(i))]
    print(f"All {len(ids)} cards enriched." if not incomplete
          else f"{len(incomplete)} card(s) still without attributes after {MAX_RETRIES} retries.")
    return results


async def main():
    if not XLSX.exists():
        print(f"Can't find {XLSX}. Run renderz_scraper.py first.")
        return
    df = pd.read_excel(XLSX)
    df["card_id"] = df["card_id"].astype(str)
    if BAND is not None:
        ov = pd.to_numeric(df["overall"], errors="coerce")
        df = df[(ov >= BAND[0]) & (ov <= BAND[1])]
    ids = list(dict.fromkeys(df["card_id"].tolist()))
    if MAX_CARDS:
        ids = ids[:MAX_CARDS]
    await enrich_cards(ids)
    save_xlsx()


if __name__ == "__main__":
    asyncio.run(main())
