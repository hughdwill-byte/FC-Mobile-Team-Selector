@echo off
REM ============================================================
REM  FC Mobile Squad Optimizer - one-click launcher (Windows)
REM  Double-click this file. First run sets everything up; after
REM  that it just starts and opens your browser.
REM  NOTE: Node.js is NOT required - this is pure Python.
REM ============================================================
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo [ERROR] Python was not found.
  echo Install Python 3.10 or newer from https://www.python.org/downloads/
  echo and make sure you tick "Add Python to PATH" during install.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating a private Python environment (first run only)...
  python -m venv .venv
  if errorlevel 1 ( echo [ERROR] Could not create the environment. & pause & exit /b 1 )
)

call ".venv\Scripts\activate.bat"

if not exist ".venv\.installed" (
  echo Installing dependencies (first run only - this can take a couple of minutes)...
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  if errorlevel 1 ( echo [ERROR] Dependency install failed - see messages above. & pause & exit /b 1 )
  echo done > ".venv\.installed"
)

echo.
echo Starting the app... your browser should open automatically.
echo Keep this window open while you use it. Close it (or press Ctrl+C) to stop.
echo.
python run.py
pause
