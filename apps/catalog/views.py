"""Management screens for the menu.

Rendered as classic Django views (not HTMX) because these pages are
administrative and don't need in-place updates. Cashiers cannot reach them;
:func:`_manager_required` enforces this at the view level in addition to the
navigation guard in :mod:`apps.pos.context_processors`.
"""

from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CategoryForm, ModifierForm, ModifierGroupForm, ProductForm
from .models import Category, Modifier, ModifierGroup, Product


def _manager_required(view):
    """Restrict a view to users where :meth:`~accounts.User.is_manager` is true."""

    @wraps(view)
    @login_required(login_url="accounts:login")
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user.is_manager():
            return HttpResponseForbidden("Нужны права администратора.")
        return view(request, *args, **kwargs)

    return wrapper


@_manager_required
def menu_dashboard(request: HttpRequest) -> HttpResponse:
    """Overview of categories, products and modifier groups."""
    context = {
        "categories": Category.objects.prefetch_related("products"),
        "modifier_groups": ModifierGroup.objects.prefetch_related("options"),
    }
    return render(request, "catalog/dashboard.html", context)


@_manager_required
def category_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    instance = get_object_or_404(Category, pk=pk) if pk else None
    form = CategoryForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Категория сохранена.")
        return redirect("catalog:dashboard")
    return render(
        request, "catalog/form.html", {"form": form, "title": "Категория"}
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
def product_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    instance = get_object_or_404(Product, pk=pk) if pk else None
    form = ProductForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Товар сохранён.")
        return redirect("catalog:dashboard")
    return render(request, "catalog/form.html", {"form": form, "title": "Товар"})


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
def modifier_group_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    instance = get_object_or_404(ModifierGroup, pk=pk) if pk else None
    form = ModifierGroupForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Группа модификаторов сохранена.")
        return redirect("catalog:dashboard")
    return render(
        request,
        "catalog/form.html",
        {"form": form, "title": "Группа модификаторов"},
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


@_manager_required
def modifier_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    instance = get_object_or_404(Modifier, pk=pk) if pk else None
    form = ModifierForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Модификатор сохранён.")
        return redirect("catalog:dashboard")
    return render(
        request, "catalog/form.html", {"form": form, "title": "Модификатор"}
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
