"""Экраны управления меню.

Отрисовываются классическими Django-вьюхами, но принимают также HTMX-запросы
для «живого» переключения доступности товаров/категорий/модификаторов без
полной перезагрузки страницы. Кассирам они недоступны;
:func:`_manager_required` гарантирует это на уровне вьюхи в дополнение к
скрытию пунктов навигации в :mod:`apps.pos.context_processors`.
"""

from __future__ import annotations

from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.orders.services import get_open_shift

from .forms import CategoryForm, ModifierForm, ModifierGroupForm, ProductForm
from .models import Category, Modifier, ModifierGroup, Product


def _manager_required(view):
    """Ограничить вьюху пользователями, у которых :meth:`~accounts.User.is_manager` истинно."""

    @wraps(view)
    @login_required(login_url="accounts:login")
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user.is_manager():
            return HttpResponseForbidden("Нужны права администратора.")
        if get_open_shift() is None:
            return redirect("pos:shift")
        return view(request, *args, **kwargs)

    return wrapper


def _safe_catalog_back(raw: str | None, fallback: str) -> str:
    """Разрешить возврат только внутрь раздела меню."""
    if raw and raw.startswith("/catalog/") and "\\" not in raw:
        return raw
    return fallback


def _parse_price(raw: str | None) -> Decimal:
    text = (raw or "0").strip().replace(",", ".")
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except Exception:
        return Decimal("0")


def _editor_context(request: HttpRequest) -> dict:
    """Три колонки редактора позиций: теги, список, карточка."""
    categories = list(
        Category.objects.annotate(n_products=Count("products")).order_by("order", "name")
    )
    groups = list(
        ModifierGroup.objects.prefetch_related("options").order_by("order", "name")
    )
    products = Product.objects.select_related("category").prefetch_related(
        "modifier_groups"
    )
    tag = None
    tag_raw = request.GET.get("tag")
    if tag_raw and tag_raw.isdigit():
        tag = next((c for c in categories if c.id == int(tag_raw)), None)
    if tag is not None:
        products = products.filter(category=tag)
    query = (request.GET.get("q") or "").strip()
    if query:
        products = products.filter(name__icontains=query)
    products = list(products.order_by("category__order", "order", "name"))

    creating = request.GET.get("new") == "1"
    selected = None
    if not creating:
        raw_id = request.GET.get("product")
        if raw_id and raw_id.isdigit():
            selected = next((p for p in products if p.id == int(raw_id)), None)
            if selected is None:
                selected = (
                    Product.objects.filter(pk=int(raw_id))
                    .select_related("category")
                    .prefetch_related("modifier_groups")
                    .first()
                )
        if selected is None and products:
            selected = products[0]
    attached = set()
    if selected is not None:
        attached = set(selected.modifier_groups.values_list("id", flat=True))
    return {
        "section": "products",
        "categories": categories,
        "groups": groups,
        "products": products,
        "total_products": sum(c.n_products for c in categories),
        "active_tag": tag,
        "query": query,
        "selected": selected,
        "creating": creating,
        "attached_ids": attached,
        "modifier_groups": groups,
    }


@_manager_required
def menu_dashboard(request: HttpRequest) -> HttpResponse:
    """Редактор позиций: список слева от карточки, фильтр по тегам."""
    return render(request, "catalog/dashboard.html", _editor_context(request))


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
        return redirect(_safe_catalog_back(request.POST.get("back"), reverse("catalog:dashboard")))
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
        return redirect(_safe_catalog_back(request.POST.get("back"), reverse("catalog:dashboard")))
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
    return render(request, "catalog/_dashboard.html", _editor_context(request))


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
        product = form.save()
        messages.success(
            request,
            "Товар обновлён." if pk else "Товар добавлен.",
        )
        if request.POST.get("stay"):
            return redirect(f"{reverse('catalog:dashboard')}?product={product.pk}")
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
    return render(request, "catalog/_dashboard.html", _editor_context(request))


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
        return redirect(_safe_catalog_back(request.POST.get("back"), reverse("catalog:groups")))
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
        return redirect(_safe_catalog_back(request.POST.get("back"), reverse("catalog:dashboard")))
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
    return render(request, "catalog/_dashboard.html", _editor_context(request))


def _groups_context(request: HttpRequest) -> dict:
    groups = list(
        ModifierGroup.objects.prefetch_related("options").order_by("order", "name")
    )
    categories = list(
        Category.objects.annotate(n_products=Count("products")).order_by("order", "name")
    )
    creating = request.GET.get("new") == "1"
    selected = None
    if not creating:
        raw_id = request.GET.get("group")
        if raw_id and raw_id.isdigit():
            selected = next((g for g in groups if g.id == int(raw_id)), None)
        if selected is None and groups:
            selected = groups[0]
    return {
        "section": "groups",
        "categories": categories,
        "total_products": sum(c.n_products for c in categories),
        "groups": groups,
        "modifier_groups": groups,
        "selected_group": selected,
        "creating_group": creating,
    }


@_manager_required
def groups_catalog(request: HttpRequest) -> HttpResponse:
    """Справочник групп допов: режим выбора, обязательность, цены, дефолт."""
    return render(request, "catalog/groups.html", _groups_context(request))


def _sync_group_options(request: HttpRequest, group: ModifierGroup) -> None:
    """Записать опции группы из одной формы редактора."""
    single = group.selection_mode == ModifierGroup.SELECTION_SINGLE
    chosen = None
    for raw in request.POST.getlist("option_id"):
        if not str(raw).isdigit():
            continue
        option = group.options.filter(pk=int(raw)).first()
        if option is None:
            continue
        name = request.POST.get(f"name_{option.id}", "").strip()
        if not name:
            continue
        option.name = name
        option.price_delta = _parse_price(request.POST.get(f"price_{option.id}"))
        option.is_default = bool(request.POST.get(f"default_{option.id}"))
        option.save()
        if option.is_default:
            chosen = option.id
    new_name = request.POST.get("new_name", "").strip()
    if new_name:
        created = Modifier.objects.create(
            group=group,
            name=new_name,
            price_delta=_parse_price(request.POST.get("new_price")),
            is_default=bool(request.POST.get("new_default")),
            is_active=True,
        )
        if created.is_default:
            chosen = created.id
    if single:
        if chosen:
            group.options.exclude(pk=chosen).update(is_default=False)
        else:
            group.options.update(is_default=False)


@_manager_required
@require_http_methods(["POST"])
def group_save(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    """Сохранить группу и её опции одним нажатием."""
    instance = get_object_or_404(ModifierGroup, pk=pk) if pk else None
    form = ModifierGroupForm(request.POST, instance=instance)
    if not form.is_valid():
        context = _groups_context(request)
        context["group_errors"] = form.errors
        context["creating_group"] = instance is None
        context["selected_group"] = instance
        return render(request, "catalog/groups.html", context)
    group = form.save()
    _sync_group_options(request, group)
    messages.success(request, "Группа допов сохранена.")
    return redirect(f"{reverse('catalog:groups')}?group={group.pk}")


@_manager_required
def tags_catalog(request: HttpRequest) -> HttpResponse:
    """Справочник тегов — это категории, вкладки на кассе."""
    categories = list(
        Category.objects.annotate(n_products=Count("products")).order_by("order", "name")
    )
    return render(
        request,
        "catalog/tags.html",
        {
            "section": "tags",
            "categories": categories,
            "total_products": sum(c.n_products for c in categories),
            "groups": [],
        },
    )
