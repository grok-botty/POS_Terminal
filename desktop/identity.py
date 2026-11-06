"""Идентификатор сборки для журнала. Без секретов и данных заказов.

Номер релиза ``v1.x`` выставляется уже после сборки exe, поэтому в журнале
главное — полный commit. Его можно сопоставить с коммитом релиза на GitHub.
Часы ноутбука сюда не входят: они на кассе прыгают.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def runtime_identity() -> dict[str, str]:
    """Вернуть ``version`` и ``commit`` текущей сборки."""
    env_version = os.environ.get("CASHMACHINE_VERSION", "").strip()
    env_commit = os.environ.get("CASHMACHINE_COMMIT", "").strip()
    baked_version, baked_commit = _baked()
    version = env_version or baked_version or "dev"
    commit = env_commit or baked_commit or _git_head() or "unknown"
    return {"version": _token(version), "commit": _token(commit)}


def _baked() -> tuple[str, str]:
    try:
        from desktop.build_info import COMMIT, VERSION
    except Exception:
        return "", ""
    return str(VERSION or ""), str(COMMIT or "")


def _git_head() -> str:
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parent.parent,
            stderr=subprocess.DEVNULL,
            timeout=1,
            text=True,
        )
    except Exception:
        return ""
    return output.strip()


def _token(value: str) -> str:
    cleaned = []
    for char in value.strip():
        if char.isalnum() or char in "._-+":
            cleaned.append(char)
        else:
            cleaned.append("_")
    token = "".join(cleaned)[:80]
    return token or "unknown"
