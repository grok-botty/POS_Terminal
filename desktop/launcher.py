"""Настольный лаунчер CashMachine.

Запускает Django-приложение в фоновом потоке на свободном loopback-порту
и открывает его в нативном окне через :mod:`pywebview`. Если pywebview
недоступен (например, пользователь не установил desktop-зависимости),
лаунчер откроет приложение в системном браузере.

Файл работает и как обычный скрипт — ``python desktop/launcher.py``, — и
как точка входа в one-file сборку PyInstaller, собранную по
:mod:`desktop.pyinstaller_spec` / ``desktop/build.bat``.

Переменная ``CASHMACHINE_HEADLESS=1`` не открывает окно: процесс только
держит локальный сервер (так GitHub Actions проверяет ``/pos/shift/``).
Выбранный URL пишется в ``cashmachine.url`` рядом с базой.
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


def _ensure_stdio() -> None:
    """Подставить настоящие stdout/stderr в оконной сборке PyInstaller.

    При ``console=False`` оба потока равны ``None``. ``print`` это терпит,
    а ``django runserver`` падает в ``OutputWrapper.write``.
    """
    frozen = bool(getattr(sys, "frozen", False))
    if sys.stdout is not None and sys.stderr is not None and not frozen:
        return
    try:
        stream = (_app_dir() / "cashmachine.log").open(
            "a", encoding="utf-8", buffering=1
        )
    except Exception:
        if sys.stdout is not None and sys.stderr is not None:
            return
        stream = open(os.devnull, "w", encoding="utf-8")
    sys.stdout = stream
    sys.stderr = stream


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


def _app_dir() -> Path:
    """Каталог пользовательских данных: база, лог и ``cashmachine.url``."""
    from config.settings import _default_db_path

    path = _default_db_path().parent
    path.mkdir(parents=True, exist_ok=True)
    return path


def _headless() -> bool:
    """Вернуть ``True``, если окно открывать не нужно (дымовой прогон CI)."""
    return os.environ.get("CASHMACHINE_HEADLESS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _publish_url(url: str) -> None:
    """Записать выбранный URL, чтобы внешний прогон нашёл порт."""
    try:
        (_app_dir() / "cashmachine.url").write_text(url + "\n", encoding="utf-8")
    except Exception:
        LOG.exception("Не удалось записать cashmachine.url")


# Оконный exe не имеет консоли: Django пишет в stdout, его нужно подставить
# до runserver. В обычном запуске из терминала потоки не трогаем.
_ensure_stdio()

# Логи пишем в файл рядом с пользовательской БД, чтобы легко собирать отчёты.
try:
    logging.basicConfig(
        filename=str(_app_dir() / "cashmachine.log"),
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


def _wait_for_server(
    url: str,
    timeout: float = 30.0,
    server: threading.Thread | None = None,
) -> bool:
    """Ждать, пока ``url`` ответит HTTP 200."""
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        if server is not None and not server.is_alive():
            LOG.error("Поток сервера завершился до ответа %s", url)
            return False
        try:
            with urllib.request.urlopen(url, timeout=0.5) as r:
                if r.status == 200:
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
    from django.db import connections

    connections.close_all()

    def _serve() -> None:
        try:
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
        except SystemExit as exc:
            LOG.error("runserver завершился: %s", exc)
        except Exception:
            LOG.exception("runserver упал")

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


def _keep_alive() -> int:
    """Держать процесс живым, пока сервер работает в фоновом потоке."""
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        return 0


def main() -> int:
    """Точка входа: используется и обычным скриптом, и PyInstaller-сборкой."""
    try:
        return _main()
    except Exception:
        LOG.exception("Не удалось запустить CashMachine")
        print(
            "Не удалось запустить CashMachine; подробности в cashmachine.log",
            file=sys.stderr,
        )
        return 1


def _main() -> int:
    """Поднять сервер и открыть окно либо остаться в headless-режиме."""
    host = "127.0.0.1"
    port = _pick_port()
    url = f"http://{host}:{port}/"
    _publish_url(url)

    LOG.info("Запуск CashMachine на %s (headless=%s)", url, _headless())
    print(f"CashMachine стартует на {url}", flush=True)

    server = _start_server(host, port)
    # One-file распаковка и migrate на холодном диске заметно дольше, чем
    # запуск из исходников.
    timeout = 120.0 if getattr(sys, "frozen", False) else 30.0
    if not _wait_for_server(url + "pos/shift/", timeout=timeout, server=server):
        print(
            "Django-сервер не поднялся; подробности в cashmachine.log",
            file=sys.stderr,
        )
        return 1

    if _headless():
        print("Режим CASHMACHINE_HEADLESS: окно не открывается.", flush=True)
        return _keep_alive()

    if not _open_window(url):
        webbrowser.open(url)
        print("Нажмите Ctrl+C для выхода.", flush=True)
        return _keep_alive()
    return 0


if __name__ == "__main__":
    sys.exit(main())
