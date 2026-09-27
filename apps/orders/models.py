"""Core order lifecycle models.

An :class:`Order` moves through the following statuses (see
:attr:`Order.Status`)::

    NEW -> IN_PROGRESS -> READY -> HANDED_OFF

The typical shift looks like this:

1. Cashier composes an :class:`Order` with :class:`OrderLine` items and
   optional per-line :class:`OrderLineModifier` selections.
2. When the customer pays, :attr:`Order.is_paid` flips to ``True`` and the
   order enters the kitchen queue (``IN_PROGRESS``).
3. Barista marks it :attr:`Order.Status.READY`. Cashier hands it off
   (:attr:`Order.Status.HANDED_OFF`).
4. At the end of the shift :func:`apps.orders.services.close_day` snapshots
   the totals into :class:`apps.analytics.models.DailySummary`.
"""

from __future__ import annotations

import string
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


def _generate_short_code() -> str:
    """Return a short human-friendly identifier such as ``B7-42``.

    We intentionally avoid characters that are easy to mistype on a phone or
    misread on a receipt (``0/O``, ``1/I``).
    """
    import secrets

    alphabet = "".join(c for c in string.ascii_uppercase + string.digits
                       if c not in "OI01")
    return f"{secrets.choice(alphabet)}{secrets.choice(alphabet)}-{secrets.randbelow(90) + 10}"


class Order(models.Model):
    """A single guest order.

    The queue view (:mod:`apps.orders.views`) filters by
    :attr:`is_paid` / :attr:`status`; the analytics app aggregates by
    :attr:`created_at` and :attr:`total_amount`.
    """

    class Status(models.TextChoices):
        NEW = "new", "Черновик"
        IN_PROGRESS = "in_progress", "В работе"
        READY = "ready", "Готов"
        HANDED_OFF = "handed_off", "Отдан"
        CANCELLED = "cancelled", "Отменён"

    class Fulfilment(models.TextChoices):
        HERE = "here", "В зале"
        TO_GO = "to_go", "С собой"

    short_code = models.CharField(
        "Номер",
        max_length=16,
        unique=True,
        default=_generate_short_code,
        db_index=True,
    )
    guest_name = models.CharField("Имя гостя", max_length=100, blank=True)
    comment = models.TextField("Комментарий", blank=True)
    status = models.CharField(
        "Статус", max_length=16, choices=Status.choices, default=Status.NEW
    )
    fulfilment = models.CharField(
        "Формат",
        max_length=8,
        choices=Fulfilment.choices,
        default=Fulfilment.HERE,
    )
    is_paid = models.BooleanField("Оплачен", default=False)
    total_amount = models.DecimalField(
        "Итого, ₽",
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders_created",
        verbose_name="Кассир",
    )
    created_at = models.DateTimeField("Создан", default=timezone.now, db_index=True)
    paid_at = models.DateTimeField("Оплачен в", null=True, blank=True)
    ready_at = models.DateTimeField("Готов в", null=True, blank=True)
    handed_off_at = models.DateTimeField("Отдан в", null=True, blank=True)

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ("-created_at",)

    def recalc_total(self) -> Decimal:
        """Recompute :attr:`total_amount` from the current lines/modifiers.

        Persists and returns the new total. Called automatically by
        :func:`apps.orders.services` whenever lines or modifiers change.
        """
        total = Decimal("0.00")
        for line in self.lines.all():
            total += line.subtotal()
        self.total_amount = total
        self.save(update_fields=["total_amount"])
        return total

    def is_active(self) -> bool:
        """Return ``True`` if the order should appear on the active queue."""
        return self.status in {
            self.Status.NEW,
            self.Status.IN_PROGRESS,
            self.Status.READY,
        }

    def waiting_seconds(self) -> int:
        """Seconds since the order was paid; used to nudge staff."""
        if not self.paid_at:
            return 0
        end = self.handed_off_at or self.ready_at or timezone.now()
        return int((end - self.paid_at).total_seconds())

    def __str__(self) -> str:  # pragma: no cover - trivial
        who = self.guest_name or "—"
        return f"{self.short_code} · {who}"


class OrderLine(models.Model):
    """A single :class:`~apps.catalog.models.Product` in an :class:`Order`."""

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="lines", verbose_name="Заказ"
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Товар",
    )
    name_snapshot = models.CharField("Название (снимок)", max_length=200)
    unit_price = models.DecimalField(
        "Цена за единицу, ₽", max_digits=8, decimal_places=2
    )
    quantity = models.PositiveIntegerField("Количество", default=1)

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"

    def subtotal(self) -> Decimal:
        """Return line total including modifier price deltas."""
        modifiers_total = sum(
            (m.price_delta_snapshot for m in self.modifiers.all()),
            Decimal("0.00"),
        )
        return (self.unit_price + modifiers_total) * self.quantity

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.name_snapshot} × {self.quantity}"


class OrderLineModifier(models.Model):
    """A single :class:`~apps.catalog.models.Modifier` attached to a line."""

    line = models.ForeignKey(
        OrderLine,
        on_delete=models.CASCADE,
        related_name="modifiers",
        verbose_name="Позиция",
    )
    modifier = models.ForeignKey(
        "catalog.Modifier",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Модификатор",
    )
    name_snapshot = models.CharField("Название (снимок)", max_length=200)
    price_delta_snapshot = models.DecimalField(
        "Изменение цены (снимок), ₽",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    class Meta:
        verbose_name = "Модификатор позиции"
        verbose_name_plural = "Модификаторы позиции"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name_snapshot
