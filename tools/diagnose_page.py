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
      const out = {};
      const firstAnchor = document.querySelector('a[href*="/player/"]');
      out.firstAnchorHref = firstAnchor ? firstAnchor.getAttribute('href') : null;
      // Walk up from the first player anchor to the row container (has several numeric cells).
      let row = firstAnchor;
      for (let i = 0; i < 8 && row; i++) {
        const nums = row.querySelectorAll ? Array.from(row.querySelectorAll('*'))
          .filter(n => /^\d{1,3}$/.test((n.textContent || '').trim())) : [];
        if (nums.length >= 5) break;
        row = row.parentElement;
      }
      out.rowHTML = row ? row.outerHTML.slice(0, 2500) : null;
      out.rowParentHTML = (row && row.parentElement) ? row.parentElement.outerHTML.slice(0, 3500) : null;
      // A table header, if present.
      const header = document.querySelector('thead') || document.querySelector('[role="row"]');
      out.headerHTML = header ? header.outerHTML.slice(0, 1500) : null;
      // Pagination controls.
      const nextBtn = Array.from(document.querySelectorAll('a,button'))
        .find(b => /next/i.test((b.textContent || '')));
      out.nextHTML = nextBtn ? nextBtn.outerHTML.slice(0, 500) : null;
      out.tables = document.querySelectorAll('table').length;
      return out;
    }""")
    print("=== firstAnchorHref ===\n", dump.get("firstAnchorHref"))
    print("=== tables on page ===", dump.get("tables"))
    print("=== headerHTML ===\n", dump.get("headerHTML"))
    print("=== rowHTML (first player row) ===\n", dump.get("rowHTML"))
    print("=== rowParentHTML ===\n", dump.get("rowParentHTML"))
    print("=== nextHTML ===\n", dump.get("nextHTML"))
    browser.close()
    p.stop()


if __name__ == "__main__":
    main()
