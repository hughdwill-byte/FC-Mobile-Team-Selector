"""
RenderZ -> Excel scraper  (v8)
==============================

Reads players from RenderZ's rendered cards. Handles:
  * OVERALL BAND      -- collect only overalls in [MIN_OVERALL, MAX_OVERALL]
  * NO SKIPPED ROWS   -- gentle, overlapping scroll so no card is missed
  * DE-DUPLICATION    -- the site lists most cards twice; identical name+overall
                         +stats within DEDUP_WINDOW rows are dropped
  * GOALKEEPERS        -- GKs use different stats. With STATS_MODE="both" the
                         script scrapes outfield players with Player stats, then
                         switches the site's stats template to Goalkeeper stats
                         and scrapes the GKs, so each gets the right stat set.

Output columns are dynamic: card_id, player_id, name, overall, position,
alt_positions, then the player stats (PAC SHO PAS DRI DEF PHY) and/or the GK
stats (DIV HAN KIC REF SPD POS ...) that were seen, then variant, club_id,
nation_id, urls.

SETUP:  pip install playwright pandas openpyxl requests pillow
        playwright install chromium
RUN:    python renderz_scraper.py            (season 24)
        python renderz_scraper.py 22         (another season)
"""

import sys
import time
import pathlib
from collections import deque

import pandas as pd
from playwright.sync_api import sync_playwright

# ============================ CONFIG (edit me) ===============================

SEASON = sys.argv[1] if len(sys.argv) > 1 else "24"

# Overall band -- the list is sorted high->low, so it starts at the top, keeps
# cards in [MIN_OVERALL, MAX_OVERALL], and stops once it passes below the min.
MAX_OVERALL = 122
MIN_OVERALL = 110

# "player"      -> only outfield players, with Player stats
# "goalkeeper"  -> only GKs, with Goalkeeper stats
# "both"        -> outfield with Player stats AND GKs with Goalkeeper stats
STATS_MODE = "both"

MAX_PLAYERS = None        # optional cap for a quick test (e.g. 300); None = all
DEDUP_WINDOW = 10         # drop identical name+overall+stats within this many rows
HEADLESS = True

# =============================================================================

SORT = "overall"          # the update script overrides this to "added"
BASE = f"https://renderz.app/{SEASON}/players"
OUT_XLSX = pathlib.Path(f"renderz_players_{SEASON}.xlsx")

# gentle scroll: small steps with heavy overlap so nothing is skipped
SCROLL_STEP = 220         # px per step (~1.8 rows; rows are ~125px) - small = no skips
SCROLL_SUBSTEPS = 6       # steps per round
SCROLL_PAUSE_MS = 280     # wait after each step for rows to render
MAX_IDLE_ROUNDS = 10      # rounds with no new cards before a sweep is "done"
MAX_SWEEPS = 8            # repeat full top->bottom sweeps until saturated
SATURATION_NEW = 3        # stop once a whole sweep adds fewer than this many new cards
FIRST_LOAD_TIMEOUT = 90

PLAYER_STATS = ["PAC", "SHO", "PAS", "DRI", "DEF", "PHY"]
# GK columns after normalising the site's new codes (GKD/GKK/GKP + REF/HAN) to the sheet's names.
GK_STATS = ["DIV", "HAN", "KIC", "REF", "POS"]

BLOCK_HOSTS = [
    "adsrvr.org", "pubmatic.com", "adnxs.com", "id5-sync.com", "crwdcntrl.net",
    "33across.com", "lngtd.com", "a-mo.net", "a-mx.com", "hadron.ad.gt",
    "pippio.com", "temu.com", "doubleclick.net", "googlesyndication.com",
    "amazon-adsystem.com", "criteo.com", "rubiconproject.com", "openx.net",
    "casalemedia.com", "sharethrough.com", "adform.net", "yieldmo.com",
    "bidswitch.net", "smartadserver.com", "taboola.com", "outbrain.com",
    "gumgum.com", "sonobi.com", "media.net", "quantcast.com", "cleverwebserver",
    "adsboosters", "scorecardresearch.com", "adroll.com", "adsafeprotected.com",
]


def is_blocked(url):
    u = url.lower()
    return any(h in u for h in BLOCK_HOSTS)


EXTRACT_JS = r"""
() => {
  const out = [];
  const anchors = document.querySelectorAll('a[href*="/player/"]');
  for (const a of anchors) out.push(__rz_extract(a));
  return out.filter(Boolean);
}
"""

# Injected once per pass. Defines the per-card extractor AND a timer that scans
# the DOM every 120ms, recording every card the moment it renders into
# window.__rzCaptured (keyed by card_id). This makes capture independent of
# Python's scroll/read cadence, so virtualized rows that briefly flash past are
# still caught -- the fix for players going missing.
INJECT_JS = r"""
() => {
  const POS = new Set(["GK","RB","LB","CB","RWB","LWB","CDM","CM","CAM","RM","LM","RW","LW","CF","ST","RF","LF"]);
  // New GK column codes -> the sheet's expected GK column names (so build_cards keeps working).
  const GKMAP = {GKD:"DIV", GKK:"KIC", GKP:"POS"};   // HAN, REF stay as-is
  window.__rz_extract = (a) => {
    const href = a.getAttribute("href") || a.href || "";
    const m = href.match(/\/player\/(\d+)/);          // numeric id only (the URL now has a -name slug)
    if (!m) return null;
    const cardId = m[1];
    const name = (a.getAttribute("aria-label") || "").trim();
    // Six stat cells: each is a <div> holding a value <span> and a label <span> (e.g. "150" + "PAC").
    const stats = {};
    a.querySelectorAll("div").forEach(d => {
      const spans = d.querySelectorAll(":scope > span");
      if (spans.length === 2) {
        const val = (spans[0].textContent || "").trim();
        let lab = (spans[1].textContent || "").trim();
        if (/^\d{1,3}$/.test(val) && /^[A-Z]{2,4}$/.test(lab)) { lab = GKMAP[lab] || lab; stats[lab] = val; }
      }
    });
    // OVR + main position live in the card-image overlay ("122 CM ...").
    const cardDiv = a.querySelector("[data-player-card]");
    const overlay = cardDiv ? (cardDiv.innerText || cardDiv.textContent || "") : "";
    const om = overlay.match(/\d{2,3}/);
    const overall = om ? om[0] : "";
    // position: first span in the row whose text is a known position code.
    let position = "";
    for (const sp of a.querySelectorAll("span")) {
      const t = (sp.textContent || "").trim().toUpperCase();
      if (POS.has(t)) { position = t; break; }
    }
    // variant + player_id from the action-shot image url.
    const actionImg = a.querySelector('img.action-shot, img[src*="/player_"]');
    const isrc = actionImg ? (actionImg.currentSrc || actionImg.src || "") : "";
    const pm = isrc.match(/player_\d+_(\d+)_(.+?)_[0-9a-f]{8,}/);
    const clubImg = a.querySelector('img.club, img[src*="/club_"]');
    const clubM = clubImg ? (clubImg.src || "").match(/club_\d+_(\d+)/) : null;
    const natImg = a.querySelector('img.nation, img[src*="/flags_"]');
    const natM = natImg ? (natImg.src || "").match(/flags_[\dx_]+_(\d+)/) : null;
    return {
      card_id: cardId, player_id: pm ? pm[1] : "",
      name, overall, position, alt_positions: "",
      variant: pm ? pm[2].replace(/_/g, " ") : "", stats,
      club_id: clubM ? clubM[1] : "", nation_id: natM ? natM[1] : "",
      player_url: href, card_image_url: isrc
    };
  };
  window.__rzCaptured = {};
  window.__rz_scan = () => {
    document.querySelectorAll('a[href*="/player/"]').forEach(a => {
      const rec = window.__rz_extract(a);
      if (!rec) return;
      const prev = window.__rzCaptured[rec.card_id];
      if (prev && Object.keys(rec.stats).length === 0
              && Object.keys(prev.stats || {}).length > 0) return;
      window.__rzCaptured[rec.card_id] = rec;
    });
  };
  if (window.__rzTimer) clearInterval(window.__rzTimer);
  window.__rzTimer = setInterval(window.__rz_scan, 80);
  window.__rz_scan();
}
"""


def start_scanner(page):
    try:
        page.evaluate(INJECT_JS)   # (re)start + reset capture for this pass
    except Exception:
        pass


def read_capture(page):
    try:
        return list(page.evaluate("() => Object.values(window.__rzCaptured || {})"))
    except Exception:
        return []


def reset_capture(page):
    try:
        page.evaluate("() => { window.__rzCaptured = {}; }")
    except Exception:
        pass


def process(result, raw, keep_fn, band, ctx, known_ids):
    for r in raw:
        cid = r.get("card_id")
        if not cid:
            continue
        ctx["encountered"].add(cid)
        try:
            ov = int(str(r.get("overall")).strip())
        except (TypeError, ValueError):
            ov = None
        if band and ov is not None:
            if ov < band[0]:
                ctx["stop"] = True
                continue
            if ov > band[1]:
                continue
            if ctx["lowest"] is None or ov < ctx["lowest"]:
                ctx["lowest"] = ov
        if known_ids is not None and cid in known_ids:
            ctx["known_set"].add(cid)
            if len(ctx["known_set"]) >= 60:
                ctx["stop"] = True
            continue
        if not keep_fn(r.get("position", "")):
            continue
        result[cid] = r   # latest render wins (correct stats for current template)


def scroll_round(page, w, h):
    page.mouse.move(w // 2, h // 2)
    for _ in range(SCROLL_SUBSTEPS):
        try:
            page.evaluate("""(step) => {
                window.scrollBy(0, step);
                document.documentElement.scrollTop += step;
                for (const el of document.querySelectorAll('*')) {
                    if (el.scrollHeight - el.clientHeight > 200 && el.clientHeight > 150) {
                        el.scrollTop += step;
                    }
                }
            }""", SCROLL_STEP)
        except Exception:
            pass
        try:
            page.mouse.wheel(0, SCROLL_STEP)
        except Exception:
            pass
        page.wait_for_timeout(SCROLL_PAUSE_MS)


def debug_dump(page, tag):
    """Print what the runner actually sees, so a headless/CI failure is diagnosable from the log."""
    try:
        info = page.evaluate(r"""() => {
          const clickable = Array.from(document.querySelectorAll('button,[role=button],a,summary'))
            .map(b => (b.innerText || b.textContent || '').trim())
            .filter(t => t && t.length < 40);
          const iframes = Array.from(document.querySelectorAll('iframe'))
            .map(f => f.src || f.title || '').filter(Boolean);
          return {
            title: document.title, url: location.href,
            players: document.querySelectorAll('a[href*="/player/"]').length,
            bodyLen: (document.body ? document.body.innerText.length : 0),
            bodyText: (document.body ? document.body.innerText : '').slice(0, 1000),
            buttons: Array.from(new Set(clickable)).slice(0, 60),
            iframes: iframes.slice(0, 8),
          };
        }""")
        print(f"  [debug:{tag}] title={info['title']!r} url={info['url']}")
        print(f"  [debug:{tag}] player anchors={info['players']}  bodyTextLen={info['bodyLen']}")
        print(f"  [debug:{tag}] iframes={info['iframes']}")
        print(f"  [debug:{tag}] clickables={info['buttons']}")
        print(f"  [debug:{tag}] body[:1000]={info['bodyText']!r}")
    except Exception as e:
        print(f"  [debug:{tag}] dump failed: {e}")


# Common consent buttons across CMPs (OneTrust, Cookiebot, Quantcast, generic). Tried in the page and in
# any consent iframe, by role/text, since a fresh CI browser hits the wall a stored local profile skips.
CONSENT_SELECTORS = [
    "#onetrust-accept-btn-handler", "#accept-recommended-btn-handler",
    "button#truste-consent-button", ".fc-cta-consent", ".qc-cmp2-summary-buttons button[mode='primary']",
    "button:has-text('Accept all')", "button:has-text('Accept All')", "button:has-text('Allow all')",
    "button:has-text('Accept')", "button:has-text('I agree')", "button:has-text('Agree')",
    "button:has-text('Consent')", "button:has-text('Got it')", "button:has-text('OK')",
    "[aria-label*='accept' i]", "[id*='consent'] button", "[class*='cookie'] button",
]


def dismiss_popups(page):
    def try_in(frame):
        clicked = False
        for sel in CONSENT_SELECTORS:
            try:
                el = frame.query_selector(sel)
                if el and el.is_visible():
                    el.click(timeout=1500)
                    clicked = True
                    page.wait_for_timeout(400)
            except Exception:
                continue
        return clicked
    hit = try_in(page)
    for fr in page.frames:                      # CMPs often render inside an iframe
        if fr is page.main_frame:
            continue
        try:
            hit = try_in(fr) or hit
        except Exception:
            continue
    return hit


def current_labels(page):
    try:
        return set(page.evaluate(r"""() => {
          const codes = new Set();
          document.querySelectorAll('span,button').forEach(e => {
            const t = (e.textContent || '').trim();
            if (/^(PAC|SHO|PAS|DRI|DEF|PHY|GKD|GKK|GKP|GKR|REF|HAN)$/.test(t)) codes.add(t);
          });
          return [...codes];
        }"""))
    except Exception:
        return set()


def template_is(page, which):
    labels = current_labels(page)
    if not labels:
        return False
    if which == "goalkeeper":
        return bool(labels & {"GKD", "GKK", "GKP", "GKR"})   # GK-only column codes
    return "PAC" in labels


def auto_switch(page, which):
    """RenderZ redesign: the stat set is chosen from the 'Columns' panel
    ('Choose the stats shown in the table' -> Player stats / Goalkeeper stats)."""
    target = "Goalkeeper stats" if which == "goalkeeper" else "Player stats"
    for opener in ["button:has-text('Columns')", "text=Columns",
                   "[aria-label*='column' i]", "button:has-text('Stats')"]:
        try:
            page.click(opener, timeout=2500)
            page.wait_for_timeout(700)
            break
        except Exception:
            continue
    for sel in [f"button:has-text('{target}')", f"text={target}", f":text('{target}')"]:
        try:
            page.click(sel, timeout=2500)
            page.wait_for_timeout(600)
            break
        except Exception:
            continue
    try:                                            # close the panel so it doesn't cover the table
        page.keyboard.press("Escape")
    except Exception:
        pass
    page.wait_for_timeout(500)


def debug_stats_controls(page):
    """Open the likely stat/column menus and dump what appears, so the goalkeeper toggle can be identified."""
    for name in ["Columns", "OVR", "Stats"]:
        try:
            el = page.query_selector(f"button:has-text('{name}')")
            if not (el and el.is_visible()):
                continue
            el.click(timeout=2000)
            page.wait_for_timeout(800)
            debug_dump(page, f"menu-{name}")
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
            page.wait_for_timeout(300)
        except Exception as e:
            print(f"  [debug] opening '{name}' menu failed: {e}")


def ensure_template(page, which):
    """Make the given stats template active. Never blocks: if it can't switch, it dumps the menus and
    returns False so the caller can skip that pass rather than hang or scrape with the wrong stats."""
    if template_is(page, which):
        return True
    for attempt in range(3):                      # the modal can be flaky; retry the whole open/pick/apply
        auto_switch(page, which)
        if template_is(page, which):
            print(f"  stats template -> {which}")
            return True
    print(f"  couldn't switch stats template to {which}; dumping the stat/column menus for diagnosis:")
    debug_dump(page, f"switch-{which}")
    debug_stats_controls(page)
    print(f"  (skipping the {which} pass this run - no manual prompt)")
    return False


def scroll_top(page):
    try:
        page.evaluate("""() => {
            window.scrollTo(0, 0);
            for (const el of document.querySelectorAll('*')) {
                if (el.scrollTop) el.scrollTop = 0;
            }
        }""")
    except Exception:
        pass
    page.wait_for_timeout(1000)


def crawl(page, result, keep_fn, band, known_ids, tag, vw, vh):
    start_scanner(page)

    # wait for first cards to appear
    deadline = time.time() + FIRST_LOAD_TIMEOUT
    while not read_capture(page) and time.time() < deadline:
        scroll_round(page, vw, vh)
    if not read_capture(page):
        # Nothing rendered yet - most often a consent wall a fresh CI browser hasn't cleared. Try again
        # to dismiss it, wait, and re-scan before giving up; dump the page state so the log explains why.
        if dismiss_popups(page):
            print(f"  [{tag}] dismissed a consent/popup; retrying...")
        page.wait_for_timeout(2500)
        start_scanner(page)
        retry_deadline = time.time() + 30
        while not read_capture(page) and time.time() < retry_deadline:
            scroll_round(page, vw, vh)

    if not read_capture(page):
        print(f"  [{tag}] no cards rendered (cookie box? empty list?)")
        debug_dump(page, tag)
        return

    # Repeat full top->bottom sweeps, unioning into `result`, until a whole
    # sweep adds almost nothing new. Each sweep resets the in-page capture so a
    # fresh pass gets fresh render timing -- different sweeps catch different
    # rows that virtualization skipped, and the union converges to complete.
    for sweep in range(1, MAX_SWEEPS + 1):
        reset_capture(page)
        scroll_top(page)
        before = len(result)
        ctx = {"lowest": None, "stop": False, "known_set": set(), "encountered": set()}
        idle, last, rounds = 0, 0, 0
        while idle < MAX_IDLE_ROUNDS and not ctx["stop"]:
            scroll_round(page, vw, vh)
            process(result, read_capture(page), keep_fn, band, ctx, known_ids)
            enc = len(ctx["encountered"])
            idle = idle + 1 if enc == last else 0
            last = enc
            rounds += 1
            if rounds % 5 == 0:
                print(f"  [{tag}] sweep {sweep}: kept {len(result)}, seen {enc} "
                      f"this sweep, lowestOVR {ctx['lowest']}")
            if MAX_PLAYERS and len(result) >= MAX_PLAYERS:
                break
        # settle + one more read to catch the last screen
        page.wait_for_timeout(500)
        process(result, read_capture(page), keep_fn, band, ctx, known_ids)
        added = len(result) - before
        print(f"  [{tag}] sweep {sweep}: +{added} new  (total {len(result)}, "
              f"lowestOVR {ctx['lowest']})")
        if MAX_PLAYERS and len(result) >= MAX_PLAYERS:
            break
        if added < SATURATION_NEW:
            print(f"  [{tag}] saturated after {sweep} sweep(s).")
            break
    else:
        print(f"  [{tag}] hit MAX_SWEEPS={MAX_SWEEPS} (raise it if still growing).")


def read_anchors(page):
    """Extract every player card currently on the page (RenderZ is now paginated, not infinite-scroll)."""
    try:
        page.evaluate(INJECT_JS)          # (re)define the per-card extractor after each navigation
    except Exception:
        pass
    try:
        return page.evaluate(EXTRACT_JS) or []
    except Exception:
        return []


MAX_PAGES = 500                            # safety cap; real stops are the OVR band / known cards / empty page


def crawl_paged(page, result, keep_fn, band, known_ids, tag, base_url, which):
    """Walk RenderZ page by page (?page=N), extracting cards until the OVR band is exhausted, we run into
    known cards (incremental), or a page comes back empty. Re-asserts the stats template each page in case a
    navigation reset it back to Player stats."""
    ctx = {"lowest": None, "stop": False, "known_set": set(), "encountered": set()}
    empty = 0
    for pnum in range(1, MAX_PAGES + 1):
        try:
            page.goto(f"{base_url}&page={pnum}", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"  [{tag}] page {pnum} load error: {e}")
            break
        page.wait_for_timeout(800)
        dismiss_popups(page)
        if which == "goalkeeper" and not template_is(page, "goalkeeper"):
            auto_switch(page, "goalkeeper")       # nav can reset the table to Player stats
        # wait for cards to render
        cards, deadline = [], time.time() + 25
        while time.time() < deadline:
            cards = read_anchors(page)
            if cards:
                break
            page.wait_for_timeout(600)
        if not cards:
            empty += 1
            print(f"  [{tag}] page {pnum}: 0 cards")
            if empty >= 2:
                print(f"  [{tag}] two empty pages - assuming end of list.")
                break
            continue
        empty = 0
        before = len(result)
        process(result, cards, keep_fn, band, ctx, known_ids)
        print(f"  [{tag}] page {pnum}: +{len(result) - before} kept "
              f"(total {len(result)}, seen {len(cards)}, lowestOVR {ctx['lowest']})")
        if ctx["stop"]:
            print(f"  [{tag}] stop condition reached on page {pnum}.")
            break
        if MAX_PLAYERS and len(result) >= MAX_PLAYERS:
            break


def scrape(sort=SORT, band=(MIN_OVERALL, MAX_OVERALL), stats_mode=STATS_MODE,
           known_ids=None, season=SEASON):
    """Run the browser crawl and return {card_id: record}. RenderZ dropped the /season/ path segment and
    switched to pagination, so we hit /players?...&page=N and turn pages instead of scrolling."""
    base_url = f"https://renderz.app/players?sortType={sort}&sortDirection=DESC"
    result = {}
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=HEADLESS, args=["--disable-blink-features=AutomationControlled"])
    # A realistic desktop UA + locale; headless Chromium's default UA is a common bot-block trigger.
    ctx = browser.new_context(
        viewport={"width": 1400, "height": 900}, locale="en-GB",
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
    )
    page = ctx.new_page()
    page.route("**/*", lambda r: r.abort() if is_blocked(r.request.url) else r.continue_())
    try:
        print(f"opening {base_url}")
        page.goto(f"{base_url}&page=1", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        if dismiss_popups(page):
            print("  dismissed a consent/cookie dialog")
        page.wait_for_timeout(1000)

        do_player = stats_mode in ("player", "both")
        do_gk = stats_mode in ("goalkeeper", "both")

        if do_player:
            print("pass: player (outfield)")
            ensure_template(page, "player")       # make sure GK columns aren't left on from a prior state
            crawl_paged(page, result, lambda pos: pos.upper() != "GK",
                        band, known_ids, "player", base_url, "player")

        if do_gk:
            print("pass: goalkeeper")
            page.goto(f"{base_url}&page=1", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)
            dismiss_popups(page)
            if ensure_template(page, "goalkeeper"):
                crawl_paged(page, result, lambda pos: pos.upper() == "GK",
                            band, known_ids, "goalkeeper", base_url, "goalkeeper")
            else:
                print("  skipped goalkeeper pass (couldn't switch to GK stats) - outfield still updated")
    except KeyboardInterrupt:
        print("\nStopping — keeping what was captured...")
    finally:
        try:
            browser.close()
        except Exception:
            pass
        try:
            p.stop()
        except Exception:
            pass
    return result


def dedup(records):
    """Drop identical name+overall+stats within DEDUP_WINDOW rows."""
    out = []
    window = deque(maxlen=DEDUP_WINDOW)
    for r in records:
        stats = r.get("stats", {}) or {}
        sig = (r.get("name"), str(r.get("overall")),
               tuple(sorted((k, str(v)) for k, v in stats.items())))
        if sig in window:
            continue
        window.append(sig)
        out.append(r)
    return out


def to_dataframe(result):
    records = dedup(list(result.values()))
    # dynamic stat columns: player stats first, then GK, then any extras
    seen = set()
    for r in records:
        seen.update((r.get("stats") or {}).keys())
    stat_cols = ([s for s in PLAYER_STATS if s in seen] +
                 [s for s in GK_STATS if s in seen] +
                 sorted(seen - set(PLAYER_STATS) - set(GK_STATS)))
    rows = []
    for r in records:
        row = {k: r.get(k) for k in ["card_id", "player_id", "name", "overall",
                                     "position", "alt_positions"]}
        st = r.get("stats") or {}
        for s in stat_cols:
            row[s] = st.get(s, "")
        for k in ["variant", "club_id", "nation_id", "player_url", "card_image_url"]:
            row[k] = r.get(k)
        rows.append(row)
    df = pd.DataFrame(rows)
    for c in ["overall"] + stat_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def save(result, out_path=OUT_XLSX):
    if not result:
        print("Nothing captured.")
        return None
    df = to_dataframe(result)
    try:
        df.to_excel(out_path, index=False)
    except PermissionError:
        alt = out_path.with_name(out_path.stem + "_new.xlsx")
        df.to_excel(alt, index=False)
        print(f"(original was open in Excel; wrote {alt} instead)")
        return df
    print(f"\nSaved {len(df)} players -> {pathlib.Path(out_path).resolve()}")
    return df


def main():
    print(f"Season {SEASON} | OVR {MAX_OVERALL}->{MIN_OVERALL} | stats={STATS_MODE}")
    print(f"(saves to {pathlib.Path.cwd()})")
    result = scrape()
    save(result)


if __name__ == "__main__":
    main()
