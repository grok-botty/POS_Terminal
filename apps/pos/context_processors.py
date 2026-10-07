"""Контекст-процессоры шаблонов, используемые по всему UI кассы."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.http import HttpRequest


def app_css_version() -> str:
    """mtime ``static/css/app.css``, чтобы браузер не держал старую таблицу.

    На демо-VPS nginx отдаёт статику с ``expires 7d``. Яндекс.Браузер тогда
    не подхватывает правки, пока не сменится query. Рестарт кассы не обязателен:
    версия читается с диска на каждый запрос.
    """
    path = Path(settings.BASE_DIR) / "static" / "css" / "app.css"
    try:
        return str(int(path.stat().st_mtime))
    except OSError:
        return "0"


def pos_globals(request: HttpRequest) -> dict:
    """Пробросить в каждый шаблон часто используемые флаги и открытую смену."""
    user = getattr(request, "user", None)
    open_shift = None
    if user is not None and user.is_authenticated:
        from apps.orders.models import Shift

        open_shift = Shift.objects.filter(is_open=True).order_by("-id").first()
    return {
        "is_manager": bool(user and user.is_authenticated and user.is_manager()),
        "app_name": "CashMachine · Касса 6ки",
        "open_shift": open_shift,
        "app_css_v": app_css_version(),
    }
