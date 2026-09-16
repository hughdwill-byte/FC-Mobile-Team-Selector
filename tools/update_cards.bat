@echo off
REM ============================================================================
REM  FC Mobile Squad Optimizer - daily card update (runs on YOUR PC)
REM ============================================================================
REM  RenderZ blocks GitHub's servers ("Unauthorised"), so the scrape must run
REM  from a normal home connection. This script scrapes the newest cards, rebuilds
REM  docs/data/cards.json, and pushes it so the live site updates - all in one go.
REM
REM  Set it up once in Task Scheduler to run daily at 11:15 (see SETUP_LOCAL_UPDATE.md).
REM  To force a full re-scan (catch 123+ OVR / anything the incremental missed):
REM      set RENDERZ_FULL=1  before running, or run  update_cards_full.bat
REM ============================================================================

setlocal
REM Move to the repo root (this script lives in tools\, so go up one level)
cd /d "%~dp0.."

echo(
echo === FC Mobile card update: %date% %time% ===

REM Get the latest first so the push can't conflict with the last run
git pull --rebase --autostash

REM Scrape RenderZ + rebuild docs/data/cards.json
python tools\renderz_update.py
if errorlevel 1 (
  echo(
  echo *** Scrape/build failed - nothing committed. See the messages above. ***
  exit /b 1
)

REM Commit + push only if something actually changed
git add docs/data/cards.json renderz_full_24.xlsx renderz_players_24.xlsx 2>nul
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "Update card database (local %date%)"
  git push
  echo(
  echo *** Pushed updated cards - the live site will refresh in ~1 minute. ***
) else (
  echo(
  echo *** No new cards - already up to date. ***
)

endlocal
