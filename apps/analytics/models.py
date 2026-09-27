"""End-of-day summaries.

Instead of recomputing per-day aggregates from :class:`~apps.orders.models.Order`
each time someone opens the analytics dashboard, the cashier calls
:func:`apps.analytics.services.close_day` which materialises a
:class:`DailySummary` for the shift. This makes the dashboard fast, historical
data immutable (even if orders are edited afterwards) and matches the
«закрытие смены» expectation of the café workflow.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models


class DailySummary(models.Model):
    """A snapshot of the metrics for a single business day."""

    date = models.DateField("Дата", unique=True, db_index=True)
    total_revenue = models.DecimalField(
        "Выручка, ₽", max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_orders = models.PositiveIntegerField("Заказов", default=0)
    paid_orders = models.PositiveIntegerField("Оплаченных", default=0)
    unpaid_orders = models.PositiveIntegerField("Не оплаченных", default=0)
    avg_check = models.DecimalField(
        "Средний чек, ₽", max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Закрыл",
    )
    closed_at = models.DateTimeField("Закрыто", auto_now_add=True)

    class Meta:
        verbose_name = "Дневная сводка"
        verbose_name_plural = "Дневные сводки"
        ordering = ("-date",)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"Сводка за {self.date}"
