from __future__ import annotations

import os
import socket
import threading
import time
import webbrowser
from pathlib import Path

from dotenv import load_dotenv


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_environment() -> None:
    """Load a local .env file without overriding explicitly supplied variables."""
    load_dotenv(_project_root() / ".env", override=False)


def _wait_for_server(host: str, port: int, timeout: float = 12.0) -> bool:
    deadline = time.monotonic() + timeout
    connect_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((connect_host, port), timeout=0.35):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def _open_browser_when_ready(host: str, port: int) -> None:
    if not _wait_for_server(host, port):
        return
    url_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    url = f"http://{url_host}:{port}"
    try:
        webbrowser.open(url, new=2)
    except Exception:
        # The URL is already printed by main(), so browser-launch failures are non-fatal.
        pass


def main() -> None:
    load_environment()

    import uvicorn

    host = os.getenv("THREADAWARE_HOST", "127.0.0.1")
    port = int(os.getenv("THREADAWARE_PORT", "8000"))
    auto_open = os.getenv("THREADAWARE_OPEN_BROWSER", "1").strip().lower() not in {"0", "false", "no", "off"}
    display_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    url = f"http://{display_host}:{port}"

    print("\nThreadAware is starting...")
    print(f"ThreadAware is running at:\n{url}\n")
    print("Press Ctrl+C to stop the local server.\n")

    if auto_open:
        threading.Thread(target=_open_browser_when_ready, args=(host, port), daemon=True).start()

    uvicorn.run("threadaware.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
