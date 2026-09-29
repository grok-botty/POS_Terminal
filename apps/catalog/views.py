"""Экраны управления меню.

Отрисовываются классическими Django-вьюхами, но принимают также HTMX-запросы
для «живого» переключения доступности товаров/категорий/модификаторов без
полной перезагрузки страницы. Кассирам они недоступны;
:func:`_manager_required` гарантирует это на уровне вьюхи в дополнение к
скрытию пунктов навигации в :mod:`apps.pos.context_processors`.
"""

from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CategoryForm, ModifierForm, ModifierGroupForm, ProductForm
from .models import Category, Modifier, ModifierGroup, Product


def _manager_required(view):
    """Ограничить вьюху пользователями, у которых :meth:`~accounts.User.is_manager` истинно."""

    @wraps(view)
    @login_required(login_url="accounts:login")
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user.is_manager():
            return HttpResponseForbidden("Нужны права администратора.")
        return view(request, *args, **kwargs)

    return wrapper


def _dashboard_context() -> dict:
    return {
        "categories": (
            Category.objects.all()
            .prefetch_related("products__modifier_groups")
            .order_by("order", "name")
        ),
        "modifier_groups": (
            ModifierGroup.objects.all()
            .prefetch_related("options")
            .order_by("order", "name")
        ),
    }


@_manager_required
def menu_dashboard(request: HttpRequest) -> HttpResponse:
    """Обзор категорий, товаров и групп модификаторов."""
    return render(request, "catalog/dashboard.html", _dashboard_context())


# ---------------------------------------------------------------------------
# Категории
# ---------------------------------------------------------------------------

@_manager_required
def category_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    instance = get_object_or_404(Category, pk=pk) if pk else None
    form = CategoryForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            "Категория обновлена." if pk else "Категория добавлена.",
        )
        return redirect("catalog:dashboard")
    return render(
        request,
        "catalog/form.html",
        {
            "form": form,
            "title": "Категория",
            "subtitle": "Изменить категорию" if pk else "Новая категория",
        },
    )


@_manager_required
def category_delete(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "Категория удалена.")
        return redirect("catalog:dashboard")
    return render(
        request,
        "catalog/confirm_delete.html",
        {"object": instance, "kind": "категорию"},
    )


@_manager_required
@require_POST
def category_toggle(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX-переключатель ``is_active`` категории."""
    category = get_object_or_404(Category, pk=pk)
    category.is_active = not category.is_active
    category.save(update_fields=["is_active"])
    return render(request, "catalog/_dashboard.html", _dashboard_context())


# ---------------------------------------------------------------------------
# Товары
# ---------------------------------------------------------------------------

@_manager_required
def product_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    instance = get_object_or_404(Product, pk=pk) if pk else None
    initial: dict = {}
    if not instance:
        cat_id = request.GET.get("category")
        if cat_id and cat_id.isdigit():
            initial["category"] = int(cat_id)
    form = ProductForm(request.POST or None, instance=instance, initial=initial)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            "Товар обновлён." if pk else "Товар добавлен.",
        )
        return redirect("catalog:dashboard")
    return render(
        request,
        "catalog/form.html",
        {
            "form": form,
            "title": "Товар",
            "subtitle": "Изменить товар" if pk else "Новый товар",
        },
    )


@_manager_required
def product_delete(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "Товар удалён.")
        return redirect("catalog:dashboard")
    return render(
        request,
        "catalog/confirm_delete.html",
        {"object": instance, "kind": "товар"},
    )


@_manager_required
@require_POST
def product_toggle(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX-переключатель ``is_active`` товара (доступность в меню)."""
    product = get_object_or_404(Product, pk=pk)
    product.is_active = not product.is_active
    product.save(update_fields=["is_active"])
    return render(request, "catalog/_dashboard.html", _dashboard_context())


# ---------------------------------------------------------------------------
# Группы модификаторов
# ---------------------------------------------------------------------------

@_manager_required
def modifier_group_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    instance = get_object_or_404(ModifierGroup, pk=pk) if pk else None
    form = ModifierGroupForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            "Группа модификаторов обновлена." if pk else "Группа модификаторов добавлена.",
        )
        return redirect("catalog:dashboard")
    return render(
        request,
        "catalog/form.html",
        {
            "form": form,
            "title": "Группа модификаторов",
            "subtitle": "Изменить группу" if pk else "Новая группа",
        },
    )


@_manager_required
def modifier_group_delete(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(ModifierGroup, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "Группа удалена.")
        return redirect("catalog:dashboard")
    return render(
        request,
        "catalog/confirm_delete.html",
        {"object": instance, "kind": "группу модификаторов"},
    )


# ---------------------------------------------------------------------------
# Модификаторы
# ---------------------------------------------------------------------------

@_manager_required
def modifier_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    instance = get_object_or_404(Modifier, pk=pk) if pk else None
    initial: dict = {}
    if not instance:
        group_id = request.GET.get("group")
        if group_id and group_id.isdigit():
            initial["group"] = int(group_id)
    form = ModifierForm(request.POST or None, instance=instance, initial=initial)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            "Модификатор обновлён." if pk else "Модификатор добавлен.",
        )
        return redirect("catalog:dashboard")
    return render(
        request,
        "catalog/form.html",
        {
            "form": form,
            "title": "Модификатор",
            "subtitle": "Изменить опцию" if pk else "Новая опция",
        },
    )


@_manager_required
def modifier_delete(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(Modifier, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "Модификатор удалён.")
        return redirect("catalog:dashboard")
    return render(
        request,
        "catalog/confirm_delete.html",
        {"object": instance, "kind": "модификатор"},
    )


@_manager_required
@require_POST
def modifier_toggle(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX-переключатель ``is_active`` опции модификатора."""
    option = get_object_or_404(Modifier, pk=pk)
    option.is_active = not option.is_active
    option.save(update_fields=["is_active"])
    return render(request, "catalog/_dashboard.html", _dashboard_context())
