"""Desktop launcher for opening the Streamlit app in a browser."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import webbrowser


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Start the app without opening a browser window.",
    )
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    if _port_is_open(args.host, args.port):
        if not args.no_browser:
            webbrowser.open(url)
        print(f"BiofilmAnalysis is already running at {url}")
        return 0

    app_path = Path(__file__).with_name("app.py")
    log_path = _log_path()
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.address",
        args.host,
        "--server.port",
        str(args.port),
        "--server.headless",
        "true",
    ]

    with log_path.open("ab") as log_file:
        subprocess.Popen(
            command,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            **_background_process_kwargs(),
        )

    if not _wait_for_server(args.host, args.port):
        print(
            "BiofilmAnalysis did not start within the expected time. "
            f"Check the launcher log at {log_path}.",
            file=sys.stderr,
        )
        return 1

    if not args.no_browser:
        webbrowser.open(url)
    print(f"BiofilmAnalysis is running at {url}")
    print(f"Launcher log: {log_path}")
    return 0


def _port_is_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _wait_for_server(host: str, port: int, timeout_seconds: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _port_is_open(host, port):
            return True
        time.sleep(0.25)
    return False


def _log_path() -> Path:
    root = Path.home() / ".biofilm-analysis"
    root.mkdir(parents=True, exist_ok=True)
    return root / "desktop-launcher.log"


def _background_process_kwargs() -> dict[str, object]:
    if os.name == "nt":
        creationflags = 0
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        return {"creationflags": creationflags}
    return {"start_new_session": True}


if __name__ == "__main__":
    raise SystemExit(main())
