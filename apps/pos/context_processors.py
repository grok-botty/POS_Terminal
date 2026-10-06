"""Контекст-процессоры шаблонов, используемые по всему UI кассы."""

from __future__ import annotations

from django.http import HttpRequest


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
    }
