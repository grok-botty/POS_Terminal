"""Короткий журнал до настройки logging.

Нужен, когда оконный exe падает раньше Django. Строка содержит pid и
идентификатор сборки. ``wall=`` — часы ноутбука и могут прыгать; порядок
внутри процесса задаёт ``mono=`` (секунды от старта интерпретатора).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def boot_dir() -> Path:
    """Каталог данных кассы: база, boot-журнал, основной журнал."""
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


def write_boot(event: str, *, limit: int = 200_000, keep: int = 100_000, **fields: object) -> None:
    """Дописать одну строку в ``cashmachine-boot.log`` и подрезать файл."""
    try:
        from desktop.identity import runtime_identity

        ident = runtime_identity()
    except Exception:
        ident = {"version": "unknown", "commit": "unknown"}
    parts = [
        f"event={_token(event)}",
        f"pid={os.getpid()}",
        f"mono={time.monotonic():.3f}",
        f"wall={time.strftime('%Y-%m-%dT%H:%M:%S')}",
        "wall_clock=unreliable",
        f"version={ident.get('version', 'unknown')}",
        f"commit={ident.get('commit', 'unknown')}",
        f"frozen={int(bool(getattr(sys, 'frozen', False)))}",
    ]
    for key, value in fields.items():
        parts.append(f"{_token(str(key))}={_token(str(value))}")
    _append_capped(boot_dir() / "cashmachine-boot.log", " ".join(parts), limit, keep)


def _append_capped(path: Path, line: str, limit: int, keep: int) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > limit:
            data = path.read_bytes()[-keep:]
            newline = data.find(b"\n")
            if newline != -1:
                data = data[newline + 1 :]
            path.write_bytes(data)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        return


def _token(value: str) -> str:
    cleaned = []
    for char in value.replace("\n", " ").replace("\r", " ").strip():
        if char.isalnum() or char in "._-+":
            cleaned.append(char)
        else:
            cleaned.append("_")
    token = "".join(cleaned)[:120]
    return token or "unknown"
