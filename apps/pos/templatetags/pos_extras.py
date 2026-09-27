"""Небольшие шаблонные помощники, используемые шаблонами кассы."""

from __future__ import annotations

from django import template

register = template.Library()


@register.filter(name="line_subtotal")
def line_subtotal(line):
    """Вернуть подытог :class:`~apps.orders.models.OrderLine`."""
    return line.subtotal()


@register.filter(name="minutes")
def minutes(seconds):
    """Отформатировать длительность в секундах как ``M мин SS с``."""
    if not seconds:
        return "—"
    m, s = divmod(int(seconds), 60)
    if m == 0:
        return f"{s} с"
    return f"{m} мин {s:02d} с"
