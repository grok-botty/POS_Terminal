"""Настольный лаунчер CashMachine.

Запускает Django-приложение в фоновом потоке на свободном loopback-порту
и открывает его в нативном окне через :mod:`pywebview`. Если pywebview
недоступен (например, пользователь не установил desktop-зависимости),
лаунчер откроет приложение в системном браузере.

Файл работает и как обычный скрипт — ``python desktop/launcher.py``, — и
как точка входа в one-file сборку PyInstaller, собранную по
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
# Настройка путей: убеждаемся, что Django находит наш проект во frozen-режиме.
# ---------------------------------------------------------------------------

def _bundle_dir() -> Path:
    """Вернуть директорию с ``manage.py`` и пакетом ``config/``.

    При запуске из PyInstaller приложение распаковывается в
    :data:`sys._MEIPASS`; иначе используется корень репозитория.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


BUNDLE = _bundle_dir()
sys.path.insert(0, str(BUNDLE))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("CASHMACHINE_DEBUG", "0")

# Логи пишем в файл рядом с пользовательской БД, чтобы легко собирать отчёты.
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
# Помощники: порт и сервер
# ---------------------------------------------------------------------------

def _pick_port(default: int = 8765) -> int:
    """Вернуть свободный порт, начиная попытки с ``default``."""
    for candidate in (default, 8766, 8767, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", candidate))
                _, port = s.getsockname()
                return port
            except OSError:
                continue
    raise RuntimeError("Не найдено свободного loopback-порта.")


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
    """Запустить Django dev-сервер на ``host:port`` в отдельном потоке."""
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
# Окно
# ---------------------------------------------------------------------------

def _open_window(url: str, title: str = "CashMachine · Касса 6ки") -> bool:
    """Открыть ``url`` в нативном окне; вернуть ``False``, если pywebview нет."""
    try:
        import webview  # type: ignore
    except ImportError:
        LOG.warning("pywebview не установлен; открываю системный браузер.")
        return False

    webview.create_window(title, url=url, width=1280, height=800, min_size=(1024, 640))
    webview.start(private_mode=False, storage_path=str(BUNDLE / ".webview"))
    return True


def main() -> int:
    """Точка входа: используется и обычным скриптом, и PyInstaller-сборкой."""
    host = "127.0.0.1"
    port = _pick_port()
    url = f"http://{host}:{port}/"

    LOG.info("Запуск CashMachine на %s", url)
    print(f"CashMachine стартует на {url}", flush=True)

    _start_server(host, port)
    if not _wait_for_server(url + "accounts/login/"):
        print(
            "Django-сервер не поднялся; подробности в cashmachine.log",
            file=sys.stderr,
        )
        return 1

    if not _open_window(url):
        webbrowser.open(url)
        print("Нажмите Ctrl+C для выхода.", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
