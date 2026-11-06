"""Журнал процесса: ротация, pid, монотонные секунды.

``asctime`` в строке — настенные часы ноутбука, они на кассе врут.
``mono=`` считается от старта процесса и порядок внутри одного pid
сохраняет. Тела запросов, cookie и имена гостей сюда не пишем.
Успешные опросы очереди не пишем: иначе журнал за смену состоит из них.
"""

from __future__ import annotations

import atexit
import logging
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path


_PROCESS_START = time.monotonic()
_HANDLER: logging.Handler | None = None

# Опрос очереди каждые 5 секунд. Успешные ответы не несут диагностики,
# а 5xx на том же пути оставляем.
_QUIET_PATHS = ("/pos/queue/", "/static/")


class QuietAccessFilter(logging.Filter):
    """Убрать успешные опросы очереди и статики из журнала доступа."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != "django.server" or record.levelno > logging.INFO:
            return True
        status = getattr(record, "status_code", None)
        message = record.getMessage()
        if status is None:
            if " 200 " not in message:
                return True
        elif int(status) != 200:
            return True
        return not any(path in message for path in _QUIET_PATHS)


class FlushingRotatingFileHandler(RotatingFileHandler):
    """Сбрасывать каждую запись: жёсткое убийство процесса не должно съедать её."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


class ProcessFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.mono = f"{time.monotonic() - _PROCESS_START:.3f}"
        return super().format(record)


class LineLogStream:
    """Собрать stdout оконного exe в тот же журнал, по строкам."""

    def __init__(self) -> None:
        self._buffer = ""
        self._logger = logging.getLogger("cashmachine.stdio")

    def write(self, data: str) -> int:
        if not data:
            return 0
        self._buffer += data
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._emit(line)
        return len(data)

    def flush(self) -> None:
        if self._buffer.strip():
            self._emit(self._buffer)
        self._buffer = ""

    def isatty(self) -> bool:
        return False

    def _emit(self, line: str) -> None:
        text = line.rstrip("\r")
        if not text.strip():
            return
        if len(text) > 4000:
            text = text[:4000] + "…"
        self._logger.info("%s", text)


def configure_process_logging(
    path: Path,
    *,
    max_bytes: int = 1_048_576,
    backup_count: int = 2,
) -> logging.Handler:
    """Повесить ротацию на корневой логгер. Повторный вызов добавляет ещё handler."""
    global _HANDLER
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = FlushingRotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.addFilter(QuietAccessFilter())
    handler.setFormatter(
        ProcessFormatter(
            "%(asctime)s mono=%(mono)s pid=%(process)d %(levelname)s %(name)s: %(message)s"
        )
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    _HANDLER = handler
    return handler


def quiet_django_server_log() -> None:
    """Забрать журнал runserver себе.

    Django вешает на ``django.server`` свой stderr и запрещает propagate.
    В оконном exe stderr — это тот же файл, и каждый опрос очереди его растит.
    """
    if _HANDLER is None:
        return
    logger = logging.getLogger("django.server")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)
    if _HANDLER not in logger.handlers:
        logger.addHandler(_HANDLER)


def install_process_hooks() -> None:
    """Отличить необработанное исключение, SystemExit и обычный выход."""
    log = logging.getLogger("cashmachine.launcher")

    def _excepthook(exc_type, exc, tb) -> None:
        if exc_type is KeyboardInterrupt:
            log.info("event=keyboard_interrupt")
        elif exc_type is SystemExit:
            code = exc.code if isinstance(exc, SystemExit) else exc
            log.info("event=system_exit code=%s", code)
        else:
            log.error("event=uncaught", exc_info=(exc_type, exc, tb))

    def _thread_hook(args: threading.ExceptHookArgs) -> None:
        if args.exc_type in (SystemExit, KeyboardInterrupt):
            return
        log.error(
            "event=thread_uncaught thread=%s",
            getattr(args.thread, "name", ""),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    def _at_exit() -> None:
        log.info("event=process_exit pid=%s", os_pid())

    sys.excepthook = _excepthook
    threading.excepthook = _thread_hook
    atexit.register(_at_exit)


def os_pid() -> int:
    import os

    return os.getpid()
