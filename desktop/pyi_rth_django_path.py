"""PyInstaller runtime hook: make the extracted project importable.

The hook runs before ``desktop/launcher.py``. It records a one-line boot
trace next to the SQLite file so a windowed exe (no console) can still be
diagnosed when startup fails before Django logging is configured.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _boot_dir() -> Path:
    db = os.environ.get("CASHMACHINE_DB_PATH")
    if db:
        folder = Path(db).expanduser().parent
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        folder = base / "CashMachine"
    elif sys.platform == "darwin":
        folder = Path.home() / "Library" / "Application Support" / "CashMachine"
    else:
        folder = Path.home() / ".local" / "share" / "cashmachine"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _boot_log(text: str) -> None:
    try:
        with (_boot_dir() / "cashmachine-boot.log").open("a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    except Exception:
        pass


if getattr(sys, "frozen", False):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault("CASHMACHINE_DEBUG", "0")
    root = getattr(sys, "_MEIPASS", "")
    if root and root not in sys.path:
        sys.path.insert(0, root)
    # console=False leaves the standard streams as None. Give them a sink
    # before Django imports; launcher.py retargets them at the app log.
    if sys.stdout is None or sys.stderr is None:
        sink = open(os.devnull, "w", encoding="utf-8")
        if sys.stdout is None:
            sys.stdout = sink
        if sys.stderr is None:
            sys.stderr = sink
    _boot_log("runtime hook ok")
