"""Небольшие шаблонные помощники, используемые шаблонами кассы."""

from __future__ import annotations

from decimal import Decimal

from django import template

register = template.Library()

_MONTHS = (
    "янв", "фев", "мар", "апр", "май", "июн",
    "июл", "авг", "сен", "окт", "ноя", "дек",
)


def _as_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or "0"))


def _plain(value) -> str:
    amount = _as_decimal(value)
    if amount == amount.to_integral():
        return str(int(amount))
    text = f"{amount:.2f}".rstrip("0").rstrip(".")
    return text


@register.filter(name="line_subtotal")
def line_subtotal(line):
    """Вернуть подытог :class:`~apps.orders.models.OrderLine`."""
    return line.subtotal()


@register.filter(name="rub")
def rub(value) -> str:
    """Сумма как на ценнике: ``270 ₽``."""
    return f"{_plain(value)} ₽"


@register.filter(name="rub_delta")
def rub_delta(value) -> str:
    """Надбавка допа: ``+30₽``. Ноль — пустая строка."""
    amount = _as_decimal(value)
    if amount == 0:
        return ""
    sign = "+" if amount > 0 else "−"
    return f"{sign}{_plain(abs(amount))}₽"


@register.filter(name="js_number")
def js_number(value) -> str:
    """Число с точкой для атрибутов, без локализации."""
    return format(_as_decimal(value), "f")


@register.filter(name="shift_chip")
def shift_chip(shift) -> str:
    """Подпись открытой смены: ``5 окт``. Дату берём у смены, не у часов."""
    if shift is None or not getattr(shift, "business_date", None):
        return ""
    day = shift.business_date
    return f"{day.day} {_MONTHS[day.month - 1]}"


@register.filter(name="visible_addons")
def visible_addons(line):
    """Допы, которые стоит показать баристе и в чеке.

    Нулевая опция «по умолчанию» (обычное молоко, обычный размер) не
    занимает строку. Платные и нестандартные опции остаются.
    """
    shown = []
    for modifier in line.modifiers.all():
        is_default = bool(getattr(modifier.modifier, "is_default", False))
        if modifier.price_delta_snapshot == 0 and is_default:
            continue
        shown.append(modifier)
    return shown


@register.filter(name="minutes")
def minutes(seconds):
    """Отформатировать длительность в секундах как ``M мин SS с``."""
    if not seconds:
        return "—"
    m, s = divmod(int(seconds), 60)
    if m == 0:
        return f"{s} с"
    return f"{m} мин {s:02d} с"
