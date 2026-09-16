# Daily card update on your PC (11:15)

RenderZ blocks GitHub's servers (it returns an **"Unauthorised"** page to any
datacenter IP), so the card scrape can't run in the cloud — it has to run from a
normal home connection. This sets up your PC to do the whole update automatically
once a day: **scrape RenderZ → rebuild `docs/data/cards.json` → push to the site.**

> **The upload is automatic.** `update_cards.bat` finishes with `git commit` and
> `git push`, so once it's scheduled there is **no manual upload step** — the
> scrape, the rebuild, and the push to GitHub all happen in one unattended run,
> and the live site refreshes about a minute later. The only requirement is that
> your PC is on at the scheduled time (see the note at the end).

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
   - Program/script: `cmd.exe`
   - **Add arguments**: `/c "tools\update_cards.bat >> tools\update_log.txt 2>&1"`
     (this runs the update and writes each run's output to `tools\update_log.txt`, so you can see what happened on unattended runs)
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

## Make sure the push works unattended

The scheduled task runs with no one watching, so `git push` must **not** pop up a
login prompt. You've pushed from this clone before, so your credentials are almost
certainly already cached — but to be safe:

- If you cloned over **HTTPS**: Git Credential Manager stores your token in Windows
  Credential Manager after the first successful push. Nothing to do.
- If `git push` ever starts asking for a username/password on this machine, do one
  manual `git push` in the repo and let it save the credentials once.
- If you cloned over **SSH** with a passphrase-protected key, either remove the
  passphrase or load it via an agent that starts with Windows, otherwise an
  unattended push will stall.

After a scheduled run, check `tools\update_log.txt` — it should end with either
"Pushed updated cards" or "No new cards — already up to date".

## Alternative: let GitHub drive it (self-hosted runner)

If you'd rather keep everything in the GitHub **Actions** tab (schedule, run
history, logs) instead of Windows Task Scheduler, install a **self-hosted runner**
on your PC. GitHub's scheduler fires the workflow, but the job executes on *your*
machine (your home IP, which RenderZ allows), and the workflow commits + pushes
automatically. Same core requirement — your PC has to be on when it fires — but
it's the most "hands-off, GitHub-native" option. Tell me if you want this and I'll
wire up a Windows-compatible workflow + the runner install steps; it's a bit more
setup than the Task Scheduler route above, which is why that's the default.

## The one unavoidable catch

Whichever route you pick, **the scrape must run from a home connection** because
RenderZ blocks datacenter IPs. There's no way to make it run while every device
you own is off — an always-on cloud box would just get "Unauthorised". If you have
a machine that's on most of the time (a home PC, a mini-PC, etc.), point the
schedule at that and it's effectively always up to date.

