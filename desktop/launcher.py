"""Настольный лаунчер CashMachine.

Запускает Django-приложение в фоновом потоке на свободном loopback-порту
и открывает его в нативном окне через :mod:`pywebview`. Если pywebview
недоступен или WebView2 не создался, лаунчер открывает системный браузер
и не гасит уже поднятый сервер.

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

# Дескриптор замка нельзя отдавать сборщику мусора: закрытый файл
# отпускает flock/msvcrt, и второй процесс начинает второй migrate.
_INSTANCE_LOCK = None
_BROWSER_OPENED = False


def _ensure_stdio() -> None:
    """В оконной сборке направить stdout/stderr в журнал.

    При ``console=False`` оба потока равны ``None``. ``print`` это терпит,
    а ``django runserver`` падает в ``OutputWrapper.write``. Пишем через
    logging, чтобы ротация не упиралась в второй открытый дескриптор файла
    (на Windows его нельзя переименовать).
    """
    frozen = bool(getattr(sys, "frozen", False))
    if sys.stdout is not None and sys.stderr is not None and not frozen:
        return
    from desktop.logsetup import LineLogStream

    stream = LineLogStream()
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
    from desktop.bootlog import boot_dir

    return boot_dir()


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
        LOG.exception("event=url_file_failed")


def _startup_timeout() -> float:
    # One-file распаковка и migrate на холодном диске заметно дольше,
    # чем запуск из исходников. Срок — monotonic, не настенные часы.
    return 120.0 if getattr(sys, "frozen", False) else 30.0


# ---------------------------------------------------------------------------
# Помощники: порт и сервер
# ---------------------------------------------------------------------------

def _pick_port(default: int = 8765) -> int:
    """Вернуть свободный порт, начиная попытки с ``default``."""
    for candidate in (default, 8766, 8767, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", candidate))
                _, port = sock.getsockname()
                return port
            except OSError:
                continue
    raise RuntimeError("Не найдено свободного loopback-порта.")


def _start_server(host: str, port: int) -> threading.Thread:
    """Запустить Django dev-сервер на ``host:port`` в отдельном потоке."""
    import django

    django.setup()

    from desktop.logsetup import quiet_django_server_log

    quiet_django_server_log()

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
            LOG.error("event=server_exit code=%s", getattr(exc, "code", exc))
        except Exception:
            LOG.exception("event=server_crash")

    thread = threading.Thread(target=_serve, daemon=True, name="django-runserver")
    thread.start()
    return thread


def _start_heartbeat(url: str, server: threading.Thread, ident: dict[str, str]) -> None:
    """Раз в минуту записать, жив ли сервер. Это не опрос очереди."""

    def _loop() -> None:
        from desktop.runtime import wait_for_http

        while True:
            time.sleep(60)
            try:
                ok, detail = wait_for_http(url, timeout=5, server=server)
                LOG.info(
                    "event=heartbeat version=%s commit=%s server_alive=%s health=%s detail=%s",
                    ident["version"],
                    ident["commit"],
                    int(server.is_alive()),
                    int(ok),
                    detail,
                )
            except Exception:
                LOG.exception("event=heartbeat_error")

    threading.Thread(target=_loop, daemon=True, name="heartbeat").start()


# ---------------------------------------------------------------------------
# Окно
# ---------------------------------------------------------------------------

def _browser_fallback(url: str) -> None:
    """Открыть браузер один раз, если окна кассы нет."""
    global _BROWSER_OPENED
    if _BROWSER_OPENED:
        return
    _BROWSER_OPENED = True
    LOG.info("event=browser_fallback")
    try:
        webbrowser.open(url)
    except Exception:
        LOG.exception("event=browser_open_failed")


def _open_window(url: str, title: str = "CashMachine · Касса 6ки") -> str:
    """Открыть окно. ``closed`` — пользователь закрыл его, сервер можно гасить.

    ``failed`` и ``unavailable`` означают, что Django ещё жив, а окна нет.
    Ошибка WebView2 (E_UNEXPECTED) pywebview только пишет в лог и не
    бросает исключение: ловим её по журналу ``pywebview`` и не называем
    это смертью сервера.
    """
    try:
        import webview  # type: ignore
    except ImportError:
        LOG.warning("event=webview_unavailable")
        return "unavailable"

    failed = {"hit": False}

    class _WebViewErrors(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            text = record.getMessage()
            if record.levelno < logging.ERROR:
                return
            if "initialization failed" not in text and "WebView2" not in text:
                return
            failed["hit"] = True
            LOG.error("event=webview_failed")
            _browser_fallback(url)

    handler = _WebViewErrors(level=logging.ERROR)
    py_logger = logging.getLogger("pywebview")
    py_logger.addHandler(handler)
    try:
        from desktop.runtime import prepare_webview_storage

        storage = prepare_webview_storage(_app_dir())
        webview.create_window(title, url=url, width=1280, height=800, min_size=(1024, 640))
        LOG.info("event=webview_start")
        webview.start(private_mode=False, storage_path=str(storage))
    except Exception:
        LOG.exception("event=webview_failed")
        return "failed"
    finally:
        py_logger.removeHandler(handler)
    if failed["hit"]:
        LOG.error("event=webview_closed reason=after_webview_error")
        return "failed"
    LOG.info("event=webview_closed reason=user")
    return "closed"


def _keep_alive() -> int:
    """Держать процесс живым, пока сервер работает в фоновом потоке."""
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        LOG.info("event=keyboard_interrupt")
        return 0


def _windows_notice(text: str) -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, "CashMachine", 0x40)
    except Exception:
        LOG.exception("event=notice_failed")


def _configure() -> None:
    from desktop.bootlog import write_boot
    from desktop.logsetup import configure_process_logging, install_process_hooks

    write_boot("launcher_main")
    configure_process_logging(_app_dir() / "cashmachine.log")
    install_process_hooks()
    _ensure_stdio()


def main() -> int:
    """Точка входа: используется и обычным скриптом, и PyInstaller-сборкой."""
    try:
        _configure()
    except Exception:
        try:
            from desktop.bootlog import write_boot

            write_boot("log_setup_failed")
        except Exception:
            pass
        raise
    try:
        return _main()
    except Exception:
        LOG.exception("event=startup_failed")
        try:
            from desktop.bootlog import write_boot

            write_boot("startup_failed")
        except Exception:
            pass
        print(
            "Не удалось запустить CashMachine; подробности в cashmachine.log",
            file=sys.stderr,
        )
        return 1


def _main() -> int:
    """Поднять сервер и открыть окно либо остаться в headless-режиме."""
    from desktop.identity import runtime_identity
    from desktop.runtime import acquire_instance_lock

    ident = runtime_identity()
    LOG.info(
        "event=process_start version=%s commit=%s pid=%s frozen=%s headless=%s",
        ident["version"],
        ident["commit"],
        os.getpid(),
        int(bool(getattr(sys, "frozen", False))),
        int(_headless()),
    )

    lock = acquire_instance_lock(_app_dir() / "cashmachine.instance.lock")
    if lock is None:
        return _attach_to_running(ident)
    return _serve(ident, lock)


def _hold_lock(lock) -> None:
    global _INSTANCE_LOCK
    _INSTANCE_LOCK = lock


def _serve(ident: dict[str, str], lock) -> int:
    """Поднять сервер. ``lock`` уже занят этим процессом."""
    from desktop.runtime import health_url, wait_for_http

    _hold_lock(lock)
    host = "127.0.0.1"
    port = _pick_port()
    url = f"http://{host}:{port}/"
    _publish_url(url)
    LOG.info("event=bind url=%s", url)
    print(f"CashMachine стартует на {url}", flush=True)

    server = _start_server(host, port)
    probe = health_url(url)
    ok, detail = wait_for_http(probe, timeout=_startup_timeout(), server=server)
    if not ok:
        LOG.error(
            "event=health_failed detail=%s server_alive=%s",
            detail,
            int(server.is_alive()),
        )
        print(
            f"Django-сервер не поднялся ({detail}); подробности в cashmachine.log",
            file=sys.stderr,
        )
        return 1

    LOG.info("event=health_ok detail=%s", detail)
    _start_heartbeat(probe, server, ident)

    if _headless():
        print("Режим CASHMACHINE_HEADLESS: окно не открывается.", flush=True)
        return _keep_alive()

    opened = _open_window(url)
    if opened == "closed":
        return 0

    _browser_fallback(url)
    if opened == "failed":
        _windows_notice(
            "Окно WebView2 не открылось. Касса открыта в браузере. "
            "Сервер Django при этом работает. Чтобы выйти, завершите "
            "CashMachine в диспетчере задач."
        )
    print("Нажмите Ctrl+C для выхода.", flush=True)
    return _keep_alive()


def _attach_to_running(ident: dict[str, str]) -> int:
    """Второй запуск не мигрирует базу и не поднимает второй сервер.

    Если первый процесс ещё стартует, ждём его health тем же сроком.
    Окно второго запуска смотрит в уже занятый URL.
    """
    from desktop.runtime import health_url, wait_for_http

    LOG.info(
        "event=already_running version=%s commit=%s pid=%s",
        ident["version"],
        ident["commit"],
        os.getpid(),
    )
    print("CashMachine уже запущена, жду существующий сервер.", flush=True)
    from desktop.runtime import acquire_instance_lock

    url_file = _app_dir() / "cashmachine.url"
    deadline = time.monotonic() + _startup_timeout()
    last = "no_url"
    while time.monotonic() < deadline:
        # Владелец мог умереть на migrate. Тогда замок свободен и этот
        # процесс поднимает сервер сам, а не ждёт до таймаута.
        lock = acquire_instance_lock(_app_dir() / "cashmachine.instance.lock")
        if lock is not None:
            LOG.info("event=lock_acquired_after_wait")
            return _serve(ident, lock)
        url = ""
        try:
            url = url_file.read_text(encoding="utf-8").strip()
        except Exception:
            url = ""
        if url:
            ok, detail = wait_for_http(health_url(url), timeout=2)
            if ok:
                LOG.info("event=attach url=%s", url)
                print(f"Открываю уже запущенную кассу: {url}", flush=True)
                if _headless():
                    return 0
                opened = _open_window(url)
                if opened != "closed":
                    _browser_fallback(url)
                return 0
            last = detail
        else:
            last = "no_url"
        time.sleep(0.3)
    LOG.error("event=already_running_unresponsive detail=%s", last)
    print(
        "CashMachine уже запущена, но сервер не отвечает; подробности в cashmachine.log",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
