"""CashMachine desktop launcher.

Runs the Django application on a random loopback port in a background
thread and opens it inside a native window using :mod:`pywebview`. When
pywebview is unavailable (e.g. the user has not installed the desktop
extras) the launcher falls back to the system browser.

The same file works both as a normal script — ``python desktop/launcher.py``
— and as the entry point of a PyInstaller one-file bundle produced by
:mod:`desktop.pyinstaller_spec` / ``desktop/build.bat``.
"""

from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


LOG = logging.getLogger("cashmachine.launcher")


# ---------------------------------------------------------------------------
# Path bootstrap: make sure Django can find our project when frozen.
# ---------------------------------------------------------------------------

def _bundle_dir() -> Path:
    """Return the directory that contains ``manage.py`` and ``config/``.

    When frozen with PyInstaller the app is extracted to
    :data:`sys._MEIPASS`; otherwise we use the repository root.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


BUNDLE = _bundle_dir()
sys.path.insert(0, str(BUNDLE))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("CASHMACHINE_DEBUG", "0")

# Configure logging to a file next to the user's DB so bug reports are easy.
try:
    from config.settings import _default_db_path  # type: ignore

    _log_dir = _default_db_path().parent
    _log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(_log_dir / "cashmachine.log"),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
except Exception:  # pragma: no cover - fall back to stderr
    logging.basicConfig(level=logging.INFO)


# ---------------------------------------------------------------------------
# Port / server helpers
# ---------------------------------------------------------------------------

def _pick_port(default: int = 8765) -> int:
    """Return a free port to bind to, preferring ``default``."""
    for candidate in (default, 8766, 8767, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", candidate))
                _, port = s.getsockname()
                return port
            except OSError:
                continue
    raise RuntimeError("No free loopback port available.")


def _wait_for_server(url: str, timeout: float = 15.0) -> bool:
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as r:
                if 200 <= r.status < 500:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def _start_server(host: str, port: int) -> threading.Thread:
    """Launch the Django development server on ``host:port`` in a thread."""
    import django

    django.setup()

    from apps.pos.bootstrap import ensure_bootstrapped

    ensure_bootstrapped()

    def _serve() -> None:
        from django.core.management import execute_from_command_line

        execute_from_command_line(
            [
                "manage.py",
                "runserver",
                f"{host}:{port}",
                "--noreload",
                "--insecure",
            ]
        )

    t = threading.Thread(target=_serve, daemon=True, name="django-runserver")
    t.start()
    return t


# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------

def _open_window(url: str, title: str = "CashMachine · Касса 6ки") -> bool:
    """Open ``url`` in a native window; return ``False`` if pywebview missing."""
    try:
        import webview  # type: ignore
    except ImportError:
        LOG.warning("pywebview not installed; opening default browser instead.")
        return False

    webview.create_window(title, url=url, width=1280, height=800, min_size=(1024, 640))
    webview.start(private_mode=False, storage_path=str(BUNDLE / ".webview"))
    return True


def main() -> int:
    """Entry point used by both the Python script and PyInstaller bundle."""
    host = "127.0.0.1"
    port = _pick_port()
    url = f"http://{host}:{port}/"

    LOG.info("Starting CashMachine on %s", url)
    print(f"CashMachine starting on {url}", flush=True)

    _start_server(host, port)
    if not _wait_for_server(url + "accounts/login/"):
        print("Django server failed to start; see cashmachine.log", file=sys.stderr)
        return 1

    if not _open_window(url):
        webbrowser.open(url)
        print("Press Ctrl+C to quit.", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
