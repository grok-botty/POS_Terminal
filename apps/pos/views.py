"""Вьюхи экрана кассы (на HTMX).

Экран — три колонки: очередь баристы, меню и текущий заказ. Товар без
групп допов попадает в заказ одним нажатием; товар с допами открывает
шторку с чипами. Любое изменение возвращает фрагмент, без полной
перезагрузки страницы.
"""

from __future__ import annotations

import csv
import random
from datetime import datetime
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.catalog.models import Category, Modifier, Product
from apps.orders import services as order_services
from apps.orders.models import Order, OrderLine

SESSION_ORDER_KEY = "current_order_id"

# Черновик и всё, что ещё лежит в очереди кассы. «Отдан» уже не правится.
EDITABLE_STATUSES = (
    Order.Status.NEW,
    Order.Status.IN_PROGRESS,
    Order.Status.READY,
    Order.Status.CANCELLED,
)

FUNNY_GUESTS = (
    "Безымянный енот",
    "Таинственный бобёр",
    "Анонимный суслик",
    "Грустный пингвин",
    "Голодный капибара",
    "Сонный барсук",
    "Безымянная квакша",
    "Сердитый хомяк",
    "Вежливый ёж",
    "Опоздавший лосёнок",
    "Тихий филин",
    "Мокрый кот",
)


def funny_guest_name() -> str:
    """Случайное имя, чтобы чек не уходил в очередь безымянным."""
    return random.choice(FUNNY_GUESTS)


def open_shift_required(view):
    """Пускать на кассу, меню и статистику только при открытой смене.

    Без смены шапка гасит вкладки, а сервер всё равно возвращает на
    «Смену»: дату нельзя подставить с часов ноутбука.
    """

    @wraps(view)
    def wrapper(request: HttpRequest, *args, **kwargs):
        if order_services.get_open_shift() is None:
            target = reverse("pos:shift")
            if request.headers.get("HX-Request"):
                resp = HttpResponse(status=204)
                resp["HX-Redirect"] = target
                return resp
            return redirect(target)
        return view(request, *args, **kwargs)

    return wrapper


def _parse_iso_date(raw: str | None):
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


_BAR_COLORS = (
    "#2e78d9",
    "#f0a04b",
    "#3cbf7a",
    "#e6c229",
    "#5b8def",
    "#8b6ad6",
    "#5bb8a8",
    "#7eb6ff",
)


# ---------------------------------------------------------------------------
# Помощники
# ---------------------------------------------------------------------------

def _session_order(request: HttpRequest) -> Order | None:
    """Заказ, открытый в правой колонке, если его ещё можно править."""
    order_id = request.session.get(SESSION_ORDER_KEY)
    if not order_id:
        return None
    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        return None
    if order.status not in EDITABLE_STATUSES:
        return None
    return order


def _get_or_create_current_order(request: HttpRequest) -> Order:
    """Вернуть заказ правой колонки: черновик или открытую карточку очереди."""
    order = _session_order(request)
    if order is not None:
        return order
    order = order_services.create_order(
        created_by=request.user,
        guest_name=funny_guest_name(),
    )
    request.session[SESSION_ORDER_KEY] = order.id
    return order


def _park_current_draft(request: HttpRequest) -> None:
    """Убрать с панели чужой черновик, не выбрасывая уже набранные позиции.

    Пустой черновик удаляется. Черновик с позициями сам уходит в очередь
    как неоплаченный — отдельного подтверждения нет. Заказ, который уже
    стоит в очереди, не трогаем: имя, комментарий и строки пишутся сразу.
    """
    order = _session_order(request)
    if order is None or order.status != Order.Status.NEW or order.is_paid:
        return
    if order.lines.exists():
        order_services.enqueue_order(order)
    else:
        order.delete()


def _line_on_panel(request: HttpRequest, line_id: int) -> OrderLine:
    """Позиция только того заказа, который сейчас открыт справа."""
    order = _get_or_create_current_order(request)
    return get_object_or_404(OrderLine, pk=line_id, order=order)


def _queue_context(request: HttpRequest) -> dict:
    return {
        "queue": order_services.barista_queue(),
        "current_order_id": request.session.get(SESSION_ORDER_KEY),
    }


def _refresh_queue(response: HttpResponse) -> HttpResponse:
    """Попросить левую колонку перерисоваться после правки открытого заказа."""
    response["HX-Trigger"] = "refreshQueue"
    return response


def _forget_current_order(request: HttpRequest) -> None:
    request.session.pop(SESSION_ORDER_KEY, None)


def _reload_order(order: Order) -> Order:
    """Перечитать заказ: после мутации префетч-кэш позиций уже устарел."""
    return Order.objects.prefetch_related("lines__modifiers__modifier").get(pk=order.pk)


def _order_panel(request: HttpRequest, order: Order | None = None) -> HttpResponse:
    if order is None:
        order = _get_or_create_current_order(request)
    return render(request, "pos/_order_panel.html", {"order": _reload_order(order)})


def _active_products():
    return (
        Product.objects.filter(is_active=True)
        .order_by("order", "name")
        .prefetch_related("modifier_groups")
    )


def _menu_context(active_category: Category | None = None) -> dict:
    categories = list(Category.objects.filter(is_active=True))
    section_qs = Category.objects.filter(is_active=True).order_by("order", "name")
    if active_category is not None:
        section_qs = section_qs.filter(pk=active_category.pk)
    section_qs = section_qs.prefetch_related(
        Prefetch("products", queryset=_active_products())
    )
    sections = [cat for cat in section_qs if cat.products.all()]
    return {
        "categories": categories,
        "active_category": active_category,
        "sections": sections,
        "show_section_headers": active_category is None,
    }


def _picker_context(product: Product, *, selected_ids: set[int] | None, line=None) -> dict:
    groups = list(
        product.modifier_groups.prefetch_related(
            Prefetch(
                "options",
                queryset=Modifier.objects.filter(is_active=True).order_by("order", "name"),
            )
        ).order_by("order", "name")
    )
    if selected_ids is None:
        selected_ids = set()
        for group in groups:
            if group.selection_mode != group.SELECTION_SINGLE:
                continue
            for option in group.options.all():
                if option.is_default:
                    selected_ids.add(option.id)
                    break
    extra = Decimal("0.00")
    for group in groups:
        for option in group.options.all():
            if option.id in selected_ids:
                extra += option.price_delta
    return {
        "product": product,
        "groups": groups,
        "selected_ids": selected_ids,
        "line": line,
        "initial_total": product.price + extra,
        "base_price": product.price,
    }


def _redirect_register() -> HttpResponse:
    resp = HttpResponse(status=204)
    resp["HX-Redirect"] = reverse("pos:register")
    return resp


# ---------------------------------------------------------------------------
# Основной экран
# ---------------------------------------------------------------------------

@login_required(login_url="accounts:login")
@open_shift_required
def register(request: HttpRequest) -> HttpResponse:
    """Полная страница кассы (первичная загрузка)."""
    category_id = request.GET.get("category")
    category = None
    if category_id and category_id.isdigit():
        category = get_object_or_404(Category, pk=category_id, is_active=True)
    context = _menu_context(category)
    context["order"] = _reload_order(_get_or_create_current_order(request))
    context.update(_queue_context(request))
    return render(request, "pos/register.html", context)


@login_required(login_url="accounts:login")
@require_http_methods(["GET", "POST"])
def shift_screen(request: HttpRequest) -> HttpResponse:
    """Открыть смену на ручную дату или закрыть её в два шага.

    Второй шаг принимает только слово ``ЗАКРЫТЬ``. Незавершённые заказы
    не отменяются: предупреждение на первом шаге предлагает оставить их
    в истории или пометить отменёнными на кассе заранее.
    """
    current = order_services.get_open_shift()
    if request.method == "POST" and request.POST.get("action") == "open":
        business_date = _parse_iso_date(request.POST.get("business_date"))
        try:
            opened = order_services.open_shift(
                business_date=business_date,
                opened_by=request.user,
            )
        except order_services.ShiftError as exc:
            return render(
                request,
                "pos/shift.html",
                {
                    "mode": "open",
                    "error": str(exc),
                    "posted_date": request.POST.get("business_date", ""),
                },
            )
        messages.success(
            request,
            f"Смена открыта на {opened.business_date:%d.%m.%Y}.",
        )
        return redirect("pos:register")

    if current is None:
        return render(request, "pos/shift.html", {"mode": "open", "posted_date": ""})

    summary = order_services.shift_summary(current)
    if request.method == "POST" and request.POST.get("action") == "close":
        try:
            order_services.close_shift(
                current,
                confirmation=request.POST.get("confirmation", ""),
                closed_by=request.user,
            )
        except order_services.ShiftError as exc:
            return render(
                request,
                "pos/shift.html",
                {
                    "mode": "confirm",
                    "shift": current,
                    "summary": summary,
                    "error": str(exc),
                    "confirmation": request.POST.get("confirmation", ""),
                },
            )
        messages.success(
            request,
            "Смена закрыта. Незавершённые заказы оставлены в её истории.",
        )
        return redirect("pos:shift")

    mode = "confirm" if request.GET.get("step") == "confirm" else "close"
    return render(
        request,
        "pos/shift.html",
        {"mode": mode, "shift": current, "summary": summary},
    )


@login_required(login_url="accounts:login")
@open_shift_required
def order_panel(request: HttpRequest) -> HttpResponse:
    """HTMX-цель: перерисовать только правую панель текущего заказа."""
    return _order_panel(request)


@login_required(login_url="accounts:login")
@open_shift_required
def products_grid(request: HttpRequest) -> HttpResponse:
    """HTMX-цель: переключить категорию без полной перезагрузки страницы."""
    category_id = request.GET.get("category")
    category = None
    if category_id and category_id.isdigit():
        category = get_object_or_404(Category, pk=category_id, is_active=True)
    return render(request, "pos/_menu.html", _menu_context(category))


@login_required(login_url="accounts:login")
@open_shift_required
def queue_fragment(request: HttpRequest) -> HttpResponse:
    """Левая колонка очереди — для цикла статуса и периодического обновления."""
    return render(request, "pos/_queue.html", _queue_context(request))


@login_required(login_url="accounts:login")
@open_shift_required
@require_http_methods(["GET"])
def queue_open(request: HttpRequest, pk: int) -> HttpResponse:
    """Открыть карточку очереди в правой колонке.

    Неоплаченный черновик с позициями перед этим сам встаёт в очередь,
    чтобы тап по чужому заказу его не стёр.
    """
    target = get_object_or_404(Order, pk=pk, status__in=EDITABLE_STATUSES)
    if request.session.get(SESSION_ORDER_KEY) != target.id:
        _park_current_draft(request)
        request.session[SESSION_ORDER_KEY] = target.id
    return _refresh_queue(_order_panel(request, target))


# ---------------------------------------------------------------------------
# Пикер модификаторов
# ---------------------------------------------------------------------------

@login_required(login_url="accounts:login")
@open_shift_required
def modifier_picker(request: HttpRequest, product_id: int) -> HttpResponse:
    """Шторка допов. У товара без групп допов позиция сразу попадает в заказ."""
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    if not product.modifier_groups.exists():
        order = _get_or_create_current_order(request)
        order_services.add_line(order, product, quantity=1)
        return _order_panel(request, order)
    return render(
        request,
        "pos/_modifier_picker.html",
        _picker_context(product, selected_ids=None),
    )


@login_required(login_url="accounts:login")
@open_shift_required
@require_http_methods(["POST"])
def add_line(request: HttpRequest, product_id: int) -> HttpResponse:
    """Добавить товар (с опциональными допами и заметкой) в текущий заказ."""
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    modifier_ids = _posted_modifier_ids(request)
    order = _get_or_create_current_order(request)
    _apply_posted_meta(request, order)
    try:
        line = order_services.add_line(
            order, product, quantity=1, modifier_ids=modifier_ids
        )
        note = request.POST.get("line_note")
        if note:
            order_services.update_line(line, note=note)
    except ValueError as exc:
        context = _picker_context(product, selected_ids=set(modifier_ids))
        context["error"] = str(exc)
        context["line_note"] = request.POST.get("line_note", "")
        resp = render(request, "pos/_modifier_picker.html", context)
        resp["HX-Retarget"] = "#picker-target"
        resp["HX-Reswap"] = "innerHTML"
        resp["HX-Keep-Picker"] = "1"
        return resp
    return _order_panel(request, order)


@login_required(login_url="accounts:login")
@open_shift_required
@require_http_methods(["GET", "POST"])
def line_edit(request: HttpRequest, line_id: int) -> HttpResponse:
    """Открыть шторку допов для уже добавленной позиции или сохранить правки."""
    line = get_object_or_404(
        OrderLine.objects.select_related("product", "order"),
        pk=line_id,
        order=_get_or_create_current_order(request),
    )
    if request.method == "GET":
        selected = set(line.modifiers.values_list("modifier_id", flat=True))
        context = _picker_context(line.product, selected_ids=selected, line=line)
        context["line_note"] = line.note
        return render(request, "pos/_modifier_picker.html", context)

    modifier_ids = _posted_modifier_ids(request)
    _apply_posted_meta(request, line.order)
    try:
        order_services.update_line(
            line,
            modifier_ids=modifier_ids,
            note=request.POST.get("line_note", ""),
        )
    except ValueError as exc:
        context = _picker_context(
            line.product, selected_ids=set(modifier_ids), line=line
        )
        context["error"] = str(exc)
        context["line_note"] = request.POST.get("line_note", "")
        resp = render(request, "pos/_modifier_picker.html", context)
        resp["HX-Retarget"] = "#picker-target"
        resp["HX-Reswap"] = "innerHTML"
        resp["HX-Keep-Picker"] = "1"
        return resp
    response = _order_panel(request, line.order)
    if line.order.status != Order.Status.NEW:
        return _refresh_queue(response)
    return response


# ---------------------------------------------------------------------------
# Действия над позициями
# ---------------------------------------------------------------------------

@login_required(login_url="accounts:login")
@open_shift_required
@require_http_methods(["POST"])
def line_inc(request: HttpRequest, line_id: int) -> HttpResponse:
    line = _line_on_panel(request, line_id)
    _apply_posted_meta(request, line.order)
    order_services.change_line_quantity(line, line.quantity + 1)
    return _refresh_queue(order_panel(request))


@login_required(login_url="accounts:login")
@open_shift_required
@require_http_methods(["POST"])
def line_dec(request: HttpRequest, line_id: int) -> HttpResponse:
    line = _line_on_panel(request, line_id)
    _apply_posted_meta(request, line.order)
    order_services.change_line_quantity(line, line.quantity - 1)
    return _refresh_queue(order_panel(request))


@login_required(login_url="accounts:login")
@open_shift_required
@require_http_methods(["POST"])
def line_remove(request: HttpRequest, line_id: int) -> HttpResponse:
    line = _line_on_panel(request, line_id)
    _apply_posted_meta(request, line.order)
    order_services.remove_line(line)
    return _refresh_queue(order_panel(request))


# ---------------------------------------------------------------------------
# Мета-данные заказа, оплата, очередь
# ---------------------------------------------------------------------------

@login_required(login_url="accounts:login")
@open_shift_required
@require_http_methods(["POST"])
def order_meta(request: HttpRequest) -> HttpResponse:
    """Обновить имя гостя, комментарий и «с собой». Панель не перерисовываем."""
    order = _get_or_create_current_order(request)
    fulfilment = None
    if request.POST.get("fulfilment_touched"):
        fulfilment = (
            Order.Fulfilment.TO_GO
            if request.POST.get("to_go")
            else Order.Fulfilment.HERE
        )
    elif request.POST.get("fulfilment") in dict(Order.Fulfilment.choices):
        fulfilment = request.POST.get("fulfilment")
    order_services.update_order_meta(
        order,
        guest_name=request.POST.get("guest_name") if "guest_name" in request.POST else None,
        comment=request.POST.get("comment") if "comment" in request.POST else None,
        fulfilment=fulfilment,
    )
    response = HttpResponse(status=204)
    if order.status != Order.Status.NEW:
        return _refresh_queue(response)
    return response


@login_required(login_url="accounts:login")
@open_shift_required
@require_http_methods(["POST"])
def order_pay(request: HttpRequest) -> HttpResponse:
    """Оплатить текущий заказ и открыть следующий чек."""
    order = _get_or_create_current_order(request)
    _apply_posted_meta(request, order)
    try:
        order_services.pay_order(order)
    except ValueError as exc:
        return _order_panel_error(request, order, str(exc))
    _forget_current_order(request)
    return _redirect_register()


@login_required(login_url="accounts:login")
@open_shift_required
@require_http_methods(["POST"])
def order_enqueue(request: HttpRequest) -> HttpResponse:
    """Поставить заказ в очередь баристы без оплаты."""
    order = _get_or_create_current_order(request)
    _apply_posted_meta(request, order)
    try:
        order_services.enqueue_order(order)
    except ValueError as exc:
        return _order_panel_error(request, order, str(exc))
    _forget_current_order(request)
    return _redirect_register()


@login_required(login_url="accounts:login")
@open_shift_required
@require_http_methods(["POST"])
def order_discard(request: HttpRequest) -> HttpResponse:
    """Закрыть правую колонку.

    Черновик без оплаты удаляется. Заказ из очереди остаётся в очереди:
    кнопка для него подписана «Новый чек» и только отпускает панель.
    """
    order_id = request.session.get(SESSION_ORDER_KEY)
    if order_id:
        Order.objects.filter(
            pk=order_id, is_paid=False, status=Order.Status.NEW
        ).delete()
        _forget_current_order(request)
    return _redirect_register()


@login_required(login_url="accounts:login")
@open_shift_required
@require_http_methods(["POST"])
def queue_cycle(request: HttpRequest, pk: int) -> HttpResponse:
    """Один тап по статусу: не готово → готово → отменено."""
    order = get_object_or_404(Order, pk=pk)
    order_services.cycle_barista_status(order)
    return queue_fragment(request)


def _posted_modifier_ids(request: HttpRequest) -> list[int]:
    """Собрать id допов: чекбоксы в ``modifiers``, радиокнопки — в ``group_<id>``."""
    ids: list[int] = []
    for key, values in request.POST.lists():
        if key == "modifiers" or key.startswith("group_"):
            ids.extend(int(value) for value in values if value.isdigit())
    return ids


def _apply_posted_meta(request: HttpRequest, order: Order) -> None:
    """Подхватить имя и комментарий, если их прислали вместе с оплатой."""
    if "guest_name" not in request.POST and "comment" not in request.POST:
        return
    order_services.update_order_meta(
        order,
        guest_name=request.POST.get("guest_name") if "guest_name" in request.POST else None,
        comment=request.POST.get("comment") if "comment" in request.POST else None,
    )


def _order_panel_error(request: HttpRequest, order: Order, message: str) -> HttpResponse:
    return render(
        request,
        "pos/_order_panel.html",
        {"order": order, "panel_error": message},
    )


def _stats_selection(request: HttpRequest):
    """Период статистики. Диапазон дат важнее готовых отрезков."""
    date_from = _parse_iso_date(request.GET.get("from"))
    date_to = _parse_iso_date(request.GET.get("to"))
    asked_for_range = bool(request.GET.get("from") or request.GET.get("to"))
    if asked_for_range:
        period = "range"
    else:
        period = request.GET.get("period") or "this"
        if period not in {"this", "7", "30", "all"}:
            period = "this"
        date_from = None
        date_to = None
    if period == "range" and date_from is None and date_to is None:
        shifts = []
    else:
        shifts = order_services.select_shifts(
            period=period, date_from=date_from, date_to=date_to
        )
    stats = order_services.aggregate_shift_stats(shifts)
    for index, row in enumerate(stats["items"]):
        row["color"] = _BAR_COLORS[index % len(_BAR_COLORS)]
    return {
        "period": period,
        "date_from": date_from,
        "date_to": date_to,
        "stats": stats,
    }


@login_required(login_url="accounts:login")
@open_shift_required
def stats(request: HttpRequest) -> HttpResponse:
    """Статистика по бизнес-датам смен, без разбивки по часам."""
    return render(request, "pos/stats.html", _stats_selection(request))


@login_required(login_url="accounts:login")
@open_shift_required
def stats_csv(request: HttpRequest) -> HttpResponse:
    """CSV выбранного периода. Файл собирается из локальной базы."""
    selection = _stats_selection(request)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="statistika.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow([
        "Дата смены",
        "Заказ",
        "Гость",
        "Статус",
        "Оплачен",
        "Позиция",
        "Кол-во",
        "Допы",
        "Сумма позиции",
    ])
    ids = [shift.id for shift in selection["stats"]["shifts"]]
    lines = (
        OrderLine.objects.filter(order__shift_id__in=ids)
        .exclude(order__status=Order.Status.NEW)
        .select_related("order__shift")
        .prefetch_related("modifiers")
        .order_by("order__shift__business_date", "order_id", "id")
    )
    for line in lines:
        order = line.order
        addons = ", ".join(m.name_snapshot for m in line.modifiers.all())
        writer.writerow([
            order.shift.business_date.isoformat() if order.shift_id else "",
            order.short_code,
            order.guest_name,
            order.barista_label() if order.status != Order.Status.HANDED_OFF else "Отдан",
            "да" if order.is_paid else "нет",
            line.name_snapshot,
            line.quantity,
            addons,
            f"{line.subtotal():.2f}",
        ])
    return response
