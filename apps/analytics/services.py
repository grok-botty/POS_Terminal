"""Aggregate helpers backing the analytics dashboard and the end-of-day flow."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, F, Sum
from django.utils import timezone

from apps.orders.models import Order, OrderLine

from .models import DailySummary


@transaction.atomic
def close_day(*, closed_by=None, target_date: date | None = None) -> DailySummary:
    """Snapshot totals for ``target_date`` (defaults to today).

    The function is idempotent: closing an already-closed day updates the
    existing snapshot instead of creating a duplicate.
    """
    day = target_date or timezone.localdate()

    orders = Order.objects.filter(created_at__date=day)
    paid = orders.filter(is_paid=True)

    total_revenue = paid.aggregate(s=Sum("total_amount"))["s"] or Decimal("0.00")
    total_orders = orders.count()
    paid_orders = paid.count()
    unpaid_orders = orders.filter(is_paid=False).count()
    avg_check = (total_revenue / paid_orders) if paid_orders else Decimal("0.00")

    summary, _ = DailySummary.objects.update_or_create(
        date=day,
        defaults={
            "total_revenue": total_revenue,
            "total_orders": total_orders,
            "paid_orders": paid_orders,
            "unpaid_orders": unpaid_orders,
            "avg_check": avg_check.quantize(Decimal("0.01")),
            "closed_by": closed_by,
        },
    )
    return summary


def revenue_series(days: int = 14) -> list[dict]:
    """Return a list of ``{date, revenue, orders}`` for the last ``days`` days."""
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    by_date = {s.date: s for s in DailySummary.objects.filter(date__gte=start, date__lte=today)}
    out: list[dict] = []
    d = start
    while d <= today:
        s = by_date.get(d)
        out.append(
            {
                "date": d,
                "revenue": s.total_revenue if s else Decimal("0.00"),
                "orders": s.total_orders if s else 0,
            }
        )
        d += timedelta(days=1)
    return out


def top_products(days: int = 30, limit: int = 10) -> list[dict]:
    """Return the top-selling products in the last ``days`` days."""
    start = timezone.localdate() - timedelta(days=days - 1)
    rows = (
        OrderLine.objects.filter(order__created_at__date__gte=start, order__is_paid=True)
        .values("name_snapshot")
        .annotate(
            qty=Sum("quantity"),
            revenue=Sum(F("unit_price") * F("quantity")),
        )
        .order_by("-revenue")[:limit]
    )
    return list(rows)


def hourly_load(days: int = 7) -> list[dict]:
    """Return counts of paid orders per hour of day for the last ``days`` days."""
    start = timezone.localdate() - timedelta(days=days - 1)
    orders = Order.objects.filter(
        created_at__date__gte=start, is_paid=True
    ).values_list("created_at", flat=True)

    buckets = {h: 0 for h in range(7, 22)}  # café hours
    for ts in orders:
        local = timezone.localtime(ts)
        h = local.hour
        buckets[h] = buckets.get(h, 0) + 1
    return [{"hour": h, "orders": buckets[h]} for h in sorted(buckets)]
