"""
Quick DOM diagnostic for the RenderZ redesign.
Opens page 1, prints the raw HTML of the table header + first couple of player rows and the pagination
controls, then exits. Fast (~15s). Paste its output back so the card-extraction selectors can be fixed
to the new layout.

RUN:  python tools\diagnose_page.py
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import renderz_scraper as rs
from playwright.sync_api import sync_playwright

URL = "https://renderz.app/players?sortType=added&sortDirection=DESC&page=1"


def main():
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(
        viewport={"width": 1400, "height": 1000}, locale="en-GB",
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"))
    page = ctx.new_page()
    page.route("**/*", lambda r: r.abort() if rs.is_blocked(r.request.url) else r.continue_())
    print(f"opening {URL}")
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3500)
    rs.dismiss_popups(page)
    page.wait_for_timeout(1500)

    dump = page.evaluate(r"""() => {
      const a = document.querySelector('a[href*="/player/"]');
      if (!a) return {none: true};
      // Strip the big player-card image block so the stat data-cells are visible.
      const clone = a.cloneNode(true);
      clone.querySelectorAll('[data-player-card]').forEach(n => n.remove());
      return {
        href: a.getAttribute('href'),
        ariaLabel: a.getAttribute('aria-label'),
        innerTextLines: (a.innerText || '').split('\n').map(s => s.trim()).filter(Boolean).slice(0, 50),
        strippedRowHTML: clone.outerHTML.slice(0, 4000),
      };
    }""")
    print("=== href ===\n", dump.get("href"))
    print("=== aria-label ===\n", dump.get("ariaLabel"))
    print("=== innerText lines (in order) ===\n", dump.get("innerTextLines"))
    print("=== row HTML with card image stripped (shows the stat cells) ===\n", dump.get("strippedRowHTML"))
    browser.close()
    p.stop()


if __name__ == "__main__":
    main()
