#!/usr/bin/env bash
# ============================================================
#  FC Mobile Squad Optimizer - one-command launcher (macOS/Linux)
#  Run:  ./start.sh    (first run sets everything up)
#  NOTE: Node.js is NOT required - this is pure Python.
# ============================================================
set -e
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "[ERROR] python3 not found. Install Python 3.10+ from https://www.python.org/downloads/"
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Creating a private Python environment (first run only)..."
  "$PY" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [ ! -f ".venv/.installed" ]; then
  echo "Installing dependencies (first run only)..."
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  touch .venv/.installed
fi

echo ""
echo "Starting the app... your browser should open automatically."
echo "Press Ctrl+C to stop."
echo ""
python run.py
