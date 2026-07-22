"""One-command launcher: starts the API and opens the app in your browser.

Usage:
    python run.py

You normally don't run this by hand - double-click start.bat (Windows) or
./start.sh (macOS/Linux), which sets up the environment first and then calls this.
"""
from __future__ import annotations

import socket
import threading
import webbrowser

import uvicorn

HOST = "127.0.0.1"


def _free_port(preferred: int = 8000) -> int:
    for port in [preferred, 8001, 8002, 8010, 8080, 0]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((HOST, port))
                return sock.getsockname()[1]
            except OSError:
                continue
    return preferred


def main() -> None:
    port = _free_port()
    url = f"http://{HOST}:{port}"

    def open_browser() -> None:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    print("=" * 56)
    print("  FC Mobile Squad Optimizer")
    print(f"  Open your browser at:  {url}")
    print("  (it should open automatically)")
    print("  Press Ctrl+C in this window to stop.")
    print("=" * 56)

    threading.Timer(1.2, open_browser).start()
    uvicorn.run("backend.main:app", host=HOST, port=port, log_level="warning")


if __name__ == "__main__":
    main()
