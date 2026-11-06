"""Замок одного процесса, ожидание HTTP и каталог WebView2.

Два exe на одной SQLite устраивают гонку migrate («table already exists»)
и взаимные блокировки. Замок держится, пока жив процесс-владелец: ОС
отпускает его при выходе, даже если часы ноутбука прыгнули.
"""

from __future__ import annotations

import os
import shutil
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


def acquire_instance_lock(path: Path):
    """Занять файл замка. ``None``, если его уже держит другой процесс.

    Дескриптор нужно сохранить: закрытие файла отпускает замок.
    Сам файл не удаляем — иначе второй процесс создаст новый и тоже
    его займёт.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+b")
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            if not handle.read(1):
                handle.seek(0)
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def health_url(root: str) -> str:
    """Лёгкая проверка сервера. Не ``/pos/shift/``: та страница пишет сессию."""
    return root.rstrip("/") + "/pos/health/"


def wait_for_http(
    url: str,
    timeout: float,
    server: threading.Thread | None = None,
    clock=time.monotonic,
) -> tuple[bool, str]:
    """Ждать HTTP 200. Срок считается по ``clock`` (по умолчанию monotonic).

    Прыжок настенных часов не обрывает и не растягивает ожидание.
    Следующий запрос начинается только когда закончился предыдущий,
    чтобы не копить брошенные соединения на сервере.
    """
    deadline = clock() + timeout
    last = "not_started"
    while clock() < deadline:
        if server is not None and not server.is_alive():
            return False, "server_thread_dead"
        remaining = deadline - clock()
        if remaining <= 0:
            break
        try:
            with urllib.request.urlopen(url, timeout=min(5.0, remaining)) as response:
                status = int(getattr(response, "status", 0) or 0)
        except urllib.error.HTTPError as exc:
            last = f"http_{exc.code}"
        except Exception as exc:
            last = type(exc).__name__
        else:
            if status == 200:
                return True, "200"
            last = f"http_{status}"
        pause = min(0.25, max(0.0, deadline - clock()))
        if pause:
            time.sleep(pause)
    return False, last


def pid_alive(pid: int) -> bool:
    """Жив ли процесс. На ошибке прав считаем, что жив, и каталог не трогаем."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        query = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
        handle = ctypes.windll.kernel32.OpenProcess(query, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def prepare_webview_storage(app_dir: Path) -> Path:
    """Каталог профиля WebView2 этого процесса.

    Общий каталог двух окон даёт E_UNEXPECTED при создании контроллера.
    Чужие каталоги умерших pid удаляем. Время модификации не смотрим:
    часы кассы ему не помощник.
    """
    root = app_dir / "webview"
    root.mkdir(parents=True, exist_ok=True)
    current = os.getpid()
    for child in list(root.iterdir()):
        if not child.is_dir():
            continue
        try:
            pid = int(child.name)
        except ValueError:
            continue
        if pid != current and not pid_alive(pid):
            shutil.rmtree(child, ignore_errors=True)
    path = root / str(current)
    path.mkdir(parents=True, exist_ok=True)
    return path
