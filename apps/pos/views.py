"""Вьюхи экрана кассы (на HTMX).

Экран кассы намеренно одностраничный: вкладки категорий, сетка товаров,
панель текущего заказа и модалка выбора модификаторов живут на одной
странице — так кассир делает меньше кликов. Любое действие, меняющее
состояние, делает HTMX-запрос и получает в ответ обновлённый фрагмент
панели заказа; при добавлении товара сетку товаров перерисовывать не
нужно.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.catalog.models import Category, Modifier, ModifierGroup, Product
from apps.orders import services as order_services
from apps.orders.models import Order, OrderLine

SESSION_ORDER_KEY = "current_order_id"


# ---------------------------------------------------------------------------
# Помощники
# ---------------------------------------------------------------------------

def _get_or_create_current_order(request: HttpRequest) -> Order:
    """Вернуть черновик заказа кассира, создав его при необходимости."""
    order_id = request.session.get(SESSION_ORDER_KEY)
    if order_id:
        try:
            order = Order.objects.get(pk=order_id)
            if order.status == Order.Status.NEW and not order.is_paid:
                return order
        except Order.DoesNotExist:
            pass
    order = order_services.create_order(created_by=request.user)
    request.session[SESSION_ORDER_KEY] = order.id
    return order


def _forget_current_order(request: HttpRequest) -> None:
    request.session.pop(SESSION_ORDER_KEY, None)


def _register_context(request: HttpRequest, active_category: Category | None = None) -> dict:
    order = _get_or_create_current_order(request)
    categories = list(Category.objects.filter(is_active=True))
    if active_category is None and categories:
        active_category = categories[0]
    products = (
        Product.objects.filter(is_active=True, category=active_category)
        .prefetch_related("modifier_groups__options")
        if active_category
        else Product.objects.none()
    )
    return {
        "categories": categories,
        "active_category": active_category,
        "products": products,
        "order": order,
        "totals_today": order_services.totals_for_today(),
    }


# ---------------------------------------------------------------------------
# Основной экран
# ---------------------------------------------------------------------------

@login_required(login_url="accounts:login")
def register(request: HttpRequest) -> HttpResponse:
    """Полная страница кассы (первичная загрузка)."""
    category_id = request.GET.get("category")
    category = None
    if category_id:
        category = get_object_or_404(Category, pk=category_id, is_active=True)
    return render(request, "pos/register.html", _register_context(request, category))


@login_required(login_url="accounts:login")
def order_panel(request: HttpRequest) -> HttpResponse:
    """HTMX-цель: перерисовать только правую панель текущего заказа."""
    order = _get_or_create_current_order(request)
    return render(
        request,
        "pos/_order_panel.html",
        {"order": order, "totals_today": order_services.totals_for_today()},
    )


@login_required(login_url="accounts:login")
def products_grid(request: HttpRequest) -> HttpResponse:
    """HTMX-цель: переключить категорию без полной перезагрузки страницы."""
    category_id = request.GET.get("category")
    category = get_object_or_404(Category, pk=category_id, is_active=True) if category_id else None
    return render(request, "pos/_products.html", _register_context(request, category))


# ---------------------------------------------------------------------------
# Пикер модификаторов
# ---------------------------------------------------------------------------

@login_required(login_url="accounts:login")
def modifier_picker(request: HttpRequest, product_id: int) -> HttpResponse:
    """Вернуть диалог выбора модификаторов для конкретного товара.

    У товаров без групп модификаторов диалог пропускается: HTMX сразу
    POST-ит на :func:`add_line`. Это оставляет быстрый путь ровно в один
    клик.
    """
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    groups = list(
        product.modifier_groups.prefetch_related("options").order_by("order", "name")
    )
    if not groups:
        # Диалог не нужен — добавляем сразу.
        order = _get_or_create_current_order(request)
        order_services.add_line(order, product, quantity=1)
        return render(
            request,
            "pos/_order_panel.html",
            {"order": order, "totals_today": order_services.totals_for_today()},
        )
    return render(
        request,
        "pos/_modifier_picker.html",
        {"product": product, "groups": groups},
    )


@login_required(login_url="accounts:login")
@require_http_methods(["POST"])
def add_line(request: HttpRequest, product_id: int) -> HttpResponse:
    """Добавить товар (с опциональными модификаторами) в текущий заказ."""
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    modifier_ids = [int(x) for x in request.POST.getlist("modifiers") if x.isdigit()]
    order = _get_or_create_current_order(request)
    try:
        order_services.add_line(order, product, quantity=1, modifier_ids=modifier_ids)
    except ValueError as exc:
        messages.error(request, str(exc))
    return render(
        request,
        "pos/_order_panel.html",
        {"order": order, "totals_today": order_services.totals_for_today()},
    )


# ---------------------------------------------------------------------------
# Действия над позициями
# ---------------------------------------------------------------------------

@login_required(login_url="accounts:login")
@require_http_methods(["POST"])
def line_inc(request: HttpRequest, line_id: int) -> HttpResponse:
    line = get_object_or_404(OrderLine, pk=line_id)
    order_services.change_line_quantity(line, line.quantity + 1)
    return order_panel(request)


@login_required(login_url="accounts:login")
@require_http_methods(["POST"])
def line_dec(request: HttpRequest, line_id: int) -> HttpResponse:
    line = get_object_or_404(OrderLine, pk=line_id)
    order_services.change_line_quantity(line, line.quantity - 1)
    return order_panel(request)


@login_required(login_url="accounts:login")
@require_http_methods(["POST"])
def line_remove(request: HttpRequest, line_id: int) -> HttpResponse:
    line = get_object_or_404(OrderLine, pk=line_id)
    order_services.remove_line(line)
    return order_panel(request)


# ---------------------------------------------------------------------------
# Мета-данные заказа и оплата
# ---------------------------------------------------------------------------

@login_required(login_url="accounts:login")
@require_http_methods(["POST"])
def order_meta(request: HttpRequest) -> HttpResponse:
    """Обновить у текущего заказа имя гостя, комментарий и «в зале/с собой»."""
    order = _get_or_create_current_order(request)
    order_services.update_order_meta(
        order,
        guest_name=request.POST.get("guest_name"),
        comment=request.POST.get("comment"),
        fulfilment=request.POST.get("fulfilment"),
    )
    return order_panel(request)


@login_required(login_url="accounts:login")
@require_http_methods(["POST"])
def order_pay(request: HttpRequest) -> HttpResponse:
    """Отметить текущий заказ оплаченным и подготовить кассу к следующему гостю."""
    order = _get_or_create_current_order(request)
    try:
        order_services.pay_order(order)
    except ValueError as exc:
        messages.error(request, str(exc))
        return order_panel(request)
    _forget_current_order(request)
    messages.success(
        request, f"Заказ {order.short_code} принят. Ждите на выдаче."
    )
    resp = HttpResponse(status=204)
    resp["HX-Redirect"] = reverse("pos:register")
    return resp


@login_required(login_url="accounts:login")
@require_http_methods(["POST"])
def order_discard(request: HttpRequest) -> HttpResponse:
    """Удалить текущий черновик заказа и открыть свежий."""
    order_id = request.session.get(SESSION_ORDER_KEY)
    if order_id:
        Order.objects.filter(pk=order_id, is_paid=False).delete()
        _forget_current_order(request)
    resp = HttpResponse(status=204)
    resp["HX-Redirect"] = reverse("pos:register")
    return resp
