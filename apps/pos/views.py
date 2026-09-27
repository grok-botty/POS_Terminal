"""POS register views (HTMX-driven).

The register is intentionally single-page: category tabs, product grid,
current-order panel and quick-add modifier picker all live on one screen so
cashiers make fewer clicks.  Every interaction that changes state issues an
HTMX request which returns the updated order-panel fragment; the product
grid does not need to re-render on add-to-order.
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
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_current_order(request: HttpRequest) -> Order:
    """Return the cashier's in-progress order, creating one if needed."""
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
# Main screen
# ---------------------------------------------------------------------------

@login_required(login_url="accounts:login")
def register(request: HttpRequest) -> HttpResponse:
    """Full register page (initial load)."""
    category_id = request.GET.get("category")
    category = None
    if category_id:
        category = get_object_or_404(Category, pk=category_id, is_active=True)
    return render(request, "pos/register.html", _register_context(request, category))


@login_required(login_url="accounts:login")
def order_panel(request: HttpRequest) -> HttpResponse:
    """HTMX target: re-render only the right-hand current-order panel."""
    order = _get_or_create_current_order(request)
    return render(
        request,
        "pos/_order_panel.html",
        {"order": order, "totals_today": order_services.totals_for_today()},
    )


@login_required(login_url="accounts:login")
def products_grid(request: HttpRequest) -> HttpResponse:
    """HTMX target: switch category without full page reload."""
    category_id = request.GET.get("category")
    category = get_object_or_404(Category, pk=category_id, is_active=True) if category_id else None
    return render(request, "pos/_products.html", _register_context(request, category))


# ---------------------------------------------------------------------------
# Modifier picker
# ---------------------------------------------------------------------------

@login_required(login_url="accounts:login")
def modifier_picker(request: HttpRequest, product_id: int) -> HttpResponse:
    """Return the modifier-picker dialog for a specific product.

    Products with no modifier groups skip the dialog: HTMX simply POSTs to
    :func:`add_line` directly. This keeps the fast path at exactly one click.
    """
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    groups = list(
        product.modifier_groups.prefetch_related("options").order_by("order", "name")
    )
    if not groups:
        # No dialog needed, add immediately.
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
    """Add a product (with optional modifiers) to the current order."""
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
# Line mutations
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
# Order meta + payment
# ---------------------------------------------------------------------------

@login_required(login_url="accounts:login")
@require_http_methods(["POST"])
def order_meta(request: HttpRequest) -> HttpResponse:
    """Update guest name / comment / here-or-to-go on the current order."""
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
    """Mark the current order paid and reset the register for the next guest."""
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
    """Delete the current draft order and start a fresh one."""
    order_id = request.session.get(SESSION_ORDER_KEY)
    if order_id:
        Order.objects.filter(pk=order_id, is_paid=False).delete()
        _forget_current_order(request)
    resp = HttpResponse(status=204)
    resp["HX-Redirect"] = reverse("pos:register")
    return resp
