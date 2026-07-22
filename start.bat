@echo off
REM ============================================================
REM  FC Mobile Squad Optimizer - one-click launcher (Windows)
REM  Double-click this file. First run sets everything up; after
REM  that it just starts and opens your browser.
REM  NOTE: Node.js is NOT required - this is pure Python.
REM  This window stays open while the app runs - closing it stops the app.
REM ============================================================
setlocal
cd /d "%~dp0"
title FC Mobile Squad Optimizer

echo ============================================================
echo   FC Mobile Squad Optimizer  -  starting up
echo ============================================================
echo.

REM --- Find a working Python (prefer 'python', fall back to the 'py' launcher) ---
set "PYEXE=python"
%PYEXE% --version >nul 2>&1
if errorlevel 1 set "PYEXE=py"
%PYEXE% --version >nul 2>&1
if errorlevel 1 goto no_python

echo Using Python:
%PYEXE% --version
echo.

REM --- Create the private environment on first run ---
if exist ".venv\Scripts\python.exe" goto have_venv
echo Creating a private Python environment. First run only...
%PYEXE% -m venv .venv
if errorlevel 1 goto venv_failed

:have_venv
call ".venv\Scripts\activate.bat"

REM --- Install dependencies on first run ---
if exist ".venv\.installed" goto have_deps
echo Installing dependencies. First run only - this can take a couple of minutes...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 goto pip_failed
echo done> ".venv\.installed"

:have_deps
echo.
echo Starting the app. Your browser should open automatically.
echo If it does not, open a browser and go to  http://127.0.0.1:8000
echo Keep THIS window open while you use it. Close it to stop the app.
echo.
python run.py
echo.
echo The app has stopped.
goto end

:no_python
echo [ERROR] Python was not found on this computer's PATH.
echo.
echo Fix: install Python 3.10 or newer from
echo      https://www.python.org/downloads/
echo and TICK the box "Add python.exe to PATH" during setup.
echo If Python is already installed, re-run its installer, choose Modify,
echo and enable "Add Python to PATH". Then run start.bat again.
goto end

:venv_failed
echo [ERROR] Could not create the Python environment. See the messages above.
echo Try deleting the .venv folder, then run start.bat again.
goto end

:pip_failed
echo [ERROR] Installing dependencies failed. Check your internet connection
echo for this first-run download, delete the .venv folder, and try again.
goto end

:end
echo.
echo ------------------------------------------------------------
echo Press any key to close this window.
pause >nul
