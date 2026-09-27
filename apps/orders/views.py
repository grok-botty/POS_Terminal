"""Очередь заказов на HTMX.

Экран выдачи живёт на отдельной странице (``/orders/``) и опрашивается HTMX,
чтобы смена всегда видела актуальное состояние без ручного обновления.
Действия над строкой («Готов», «Отдан», отмена) возвращают обновлённый
фрагмент, поэтому DOM остаётся синхронным без полной перезагрузки страницы.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from . import services
from .models import Order


def _queue_context() -> dict:
    active = (
        Order.objects.filter(
            status__in=[
                Order.Status.IN_PROGRESS,
                Order.Status.READY,
            ]
        )
        .prefetch_related("lines__modifiers")
        .order_by("paid_at")
    )
    handed = (
        Order.objects.filter(status=Order.Status.HANDED_OFF)
        .order_by("-handed_off_at")[:10]
    )
    return {"active_orders": list(active), "recent_handoffs": list(handed)}


@login_required(login_url="accounts:login")
def queue(request: HttpRequest) -> HttpResponse:
    """Полная страница очереди."""
    return render(request, "orders/queue.html", _queue_context())


@login_required(login_url="accounts:login")
def queue_fragment(request: HttpRequest) -> HttpResponse:
    """Цель HTMX-polling — перерисовывает только списки очереди."""
    return render(request, "orders/_queue.html", _queue_context())


@login_required(login_url="accounts:login")
@require_http_methods(["POST"])
def action_ready(request: HttpRequest, pk: int) -> HttpResponse:
    services.mark_ready(get_object_or_404(Order, pk=pk))
    return render(request, "orders/_queue.html", _queue_context())


@login_required(login_url="accounts:login")
@require_http_methods(["POST"])
def action_all_ready(request: HttpRequest) -> HttpResponse:
    services.mark_all_ready()
    return render(request, "orders/_queue.html", _queue_context())


@login_required(login_url="accounts:login")
@require_http_methods(["POST"])
def action_handoff(request: HttpRequest, pk: int) -> HttpResponse:
    services.hand_off(get_object_or_404(Order, pk=pk))
    return render(request, "orders/_queue.html", _queue_context())


@login_required(login_url="accounts:login")
@require_http_methods(["POST"])
def action_cancel(request: HttpRequest, pk: int) -> HttpResponse:
    services.cancel_order(get_object_or_404(Order, pk=pk))
    return render(request, "orders/_queue.html", _queue_context())
