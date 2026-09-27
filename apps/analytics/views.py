"""Analytics dashboard and end-of-day close action.

Only managers can see the dashboard; regular cashiers can trigger the daily
close from the POS screen if allowed.
"""

from __future__ import annotations

from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from . import services
from .models import DailySummary


def _manager_required(view):
    @wraps(view)
    @login_required(login_url="accounts:login")
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user.is_manager():
            return HttpResponseForbidden("Нужны права администратора.")
        return view(request, *args, **kwargs)

    return wrapper


@_manager_required
def dashboard(request: HttpRequest) -> HttpResponse:
    days = int(request.GET.get("days", "14"))
    days = max(1, min(days, 90))
    series = services.revenue_series(days=days)
    max_revenue = max((row["revenue"] for row in series), default=Decimal("0.00"))
    for row in series:
        if max_revenue > 0:
            row["bar_pct"] = int(Decimal("100") * row["revenue"] / max_revenue)
        else:
            row["bar_pct"] = 0

    context = {
        "days": days,
        "series": series,
        "top_products": services.top_products(days=days, limit=10),
        "hourly_load": services.hourly_load(days=min(days, 30)),
        "summaries": DailySummary.objects.all()[:14],
    }
    return render(request, "analytics/dashboard.html", context)


@login_required(login_url="accounts:login")
@require_http_methods(["POST"])
def close_day_view(request: HttpRequest) -> HttpResponse:
    """Close today's shift and redirect to the register."""
    summary = services.close_day(closed_by=request.user)
    messages.success(
        request,
        f"Смена {summary.date} закрыта. Выручка: {summary.total_revenue} ₽, "
        f"заказов: {summary.total_orders}.",
    )
    if request.user.is_manager():
        return redirect("analytics:dashboard")
    return redirect("pos:register")
