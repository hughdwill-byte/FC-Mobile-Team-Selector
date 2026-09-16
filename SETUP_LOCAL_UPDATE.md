# Daily card update on your PC (11:15)

RenderZ blocks GitHub's servers (it returns an **"Unauthorised"** page to any
datacenter IP), so the card scrape can't run in the cloud — it has to run from a
normal home connection. This sets up your PC to do the whole update automatically
once a day: **scrape RenderZ → rebuild `docs/data/cards.json` → push to the site.**

## One-time prerequisites

You already run the scraper locally, so most of this is done. Confirm:

1. **This repo is cloned on your PC** and you can `git push` from it (you've pushed before, so you're set).
2. **Python + the scraper deps** are installed:
   ```
   pip install -r tools/requirements-scraper.txt
   python -m playwright install chromium
   ```
3. **Test the script once** — open the repo in File Explorer and double-click:
   ```
   tools\update_cards.bat
   ```
   You should see it scrape, then either "Pushed updated cards" or "No new cards — already up to date". If that works by hand, scheduling it is trivial.

## Schedule it for 11:15 every day (Windows Task Scheduler)

1. Press **Start**, type **Task Scheduler**, open it.
2. Right-hand panel → **Create Task…** (not *Basic Task* — we want the extra options).
3. **General** tab:
   - Name: `FC Mobile card update`
   - Tick **Run whether user is logged on or not** (so it runs even if you're not signed in) — optional.
4. **Triggers** tab → **New…**:
   - Begin the task: **On a schedule**, **Daily**, Start time **11:15:00**, Recur every **1 day** → **OK**.
5. **Actions** tab → **New…**:
   - Action: **Start a program**
   - Program/script: browse to your clone's `tools\update_cards.bat`
     (e.g. `C:\Users\you\FC-Mobile-Team-Selector\tools\update_cards.bat`)
   - **Start in**: the repo root folder (e.g. `C:\Users\you\FC-Mobile-Team-Selector`) — this matters so git runs in the repo.
   - **OK**.
6. **Settings** tab (recommended):
   - Tick **Run task as soon as possible after a scheduled start is missed** (so it still runs if the PC was off at 11:15).
   - Tick **Wake the computer to run this task** if you want it to run while asleep.
7. **OK**. Enter your Windows password if prompted.

That's it. Every day at 11:15 (your local time — no daylight-saving headaches, since it's your PC's clock) it scrapes, rebuilds `cards.json`, and pushes. The live site refreshes about a minute after each push.

> **Your PC must be on and awake at 11:15** for it to run (or shortly after, if you ticked "run a missed task"). If your machine is often off, run it by hand whenever you like — just double-click `tools\update_cards.bat`.

## Manual runs

- **Normal update:** double-click `tools\update_cards.bat`
- **Full re-scan** (catches new high-rated 123+ cards or anything the quick scan skipped): double-click `tools\update_cards_full.bat`

## If a run finds nothing but you know there are new cards

Use the **full** script (`update_cards_full.bat`). It re-checks the whole overall
band (100–200) instead of trusting RenderZ's "recently added" ordering.
