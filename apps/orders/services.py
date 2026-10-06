"""Бизнес-логика приложения orders.

Все мутации :class:`~apps.orders.models.Order` идут через этот модуль, чтобы
шаблоны и вьюхи оставались тонкими. Каждая функция транзакционна и безопасна
для вызова из shell.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable

from django.db import transaction
from django.db.models import Case, IntegerField, Q, Sum, When
from django.utils import timezone

from apps.catalog.models import Modifier, ModifierGroup, Product

from .models import Order, OrderLine, OrderLineModifier, Shift


# Точная фраза второго шага закрытия. Регистр и буквы обязательны.
CLOSE_PHRASE = "ЗАКРЫТЬ"

# «Выдано» — бариста отметил «Готово» или заказ уже отдан со старого экрана.
ISSUED_STATUSES = (Order.Status.READY, Order.Status.HANDED_OFF)


class ShiftError(ValueError):
    """Смену нельзя открыть или закрыть в текущем виде."""


def get_open_shift() -> Shift | None:
    """Вернуть открытую смену или ``None``.

    Бизнес-дата берётся только отсюда. Если смены нет, вызывающий не
    подставляет системную дату.
    """
    return Shift.objects.filter(is_open=True).order_by("-id").first()


@transaction.atomic
def open_shift(*, business_date: date, opened_by=None, cashier_name: str = "") -> Shift:
    """Открыть смену на вручную указанную дату.

    Системные часы не читаются: ``business_date`` обязана прийти от
    кассира. ``opened_at`` остаётся пустым — ноутбук с сломанными часами
    не должен оставлять ложную метку. Вторая открытая смена запрещена.
    ``cashier_name`` — подпись в шапке; если её не прислали, берётся логин.
    Стартовой кассы нет.
    """
    if not isinstance(business_date, date):
        raise ShiftError("Укажите дату смены.")
    if Shift.objects.filter(is_open=True).exists():
        raise ShiftError("Смена уже открыта. Сначала закройте её.")
    name = (cashier_name or "").strip()
    if not name and opened_by is not None and getattr(opened_by, "is_authenticated", True):
        name = (opened_by.get_full_name() or opened_by.get_username() or "").strip()
    return Shift.objects.create(
        business_date=business_date,
        is_open=True,
        opened_by=opened_by if getattr(opened_by, "is_authenticated", True) else None,
        cashier_name=name[:100],
    )


def shift_summary(shift: Shift) -> dict:
    """Сводка для первого шага закрытия. Черновики в счёт не идут.

    ``paid`` — сумма оплаченных и не отменённых заказов (та же выручка,
    что на экране статистики). ``unfinished`` — ещё «не готово»: закрытие
    их не трогает.
    """
    qs = shift.orders.exclude(status=Order.Status.NEW)
    paid = qs.filter(is_paid=True).exclude(status=Order.Status.CANCELLED)
    revenue = paid.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
    return {
        "orders": qs.count(),
        "paid": revenue,
        "cancelled": qs.filter(status=Order.Status.CANCELLED).count(),
        "unfinished": qs.filter(status=Order.Status.IN_PROGRESS).count(),
    }


@transaction.atomic
def close_shift(shift: Shift, *, confirmation: str, closed_by=None) -> Shift:
    """Закрыть смену, если кассир ввёл ровно :data:`CLOSE_PHRASE`.

    Незавершённые заказы не отменяются и не блокируют закрытие: бариста
    либо пометил их раньше, либо они остаются в истории смены. ``closed_at``
    не ставится по часам ноутбука.
    """
    shift = Shift.objects.select_for_update().get(pk=shift.pk)
    if not shift.is_open:
        raise ShiftError("Смена уже закрыта.")
    if (confirmation or "").strip() != CLOSE_PHRASE:
        raise ShiftError("Чтобы закрыть смену, введите ЗАКРЫТЬ.")
    shift.is_open = False
    shift.closed_by = closed_by
    shift.save(update_fields=["is_open", "closed_by"])
    return shift


def select_shifts(
    *,
    period: str = "this",
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[Shift]:
    """Смены для статистики.

    Диапазон дат режет по :attr:`Shift.business_date`, не по ``created_at``.
    «7 смен» и «30 смен» — это последние N записей смен, а не календарные
    дни. «Эта смена» — только открытая.
    """
    qs = Shift.objects.all()
    if date_from is not None or date_to is not None:
        if date_from is not None:
            qs = qs.filter(business_date__gte=date_from)
        if date_to is not None:
            qs = qs.filter(business_date__lte=date_to)
        return list(qs.order_by("-business_date", "-id"))
    ordered = qs.order_by("-business_date", "-id")
    if period == "this":
        current = get_open_shift()
        return [current] if current is not None else []
    if period == "7":
        return list(ordered[:7])
    if period == "30":
        return list(ordered[:30])
    return list(ordered)


def aggregate_shift_stats(shifts: Iterable[Shift]) -> dict:
    """Свести заказы выбранных смен. Часы ноутбука не участвуют.

    * «Выдано» — статус «Готово» или «Отдан».
    * «Выручка» — сумма оплаченных и не отменённых заказов, допы уже
      внутри ``total_amount``.
    * «Средний чек» — выручка / выдано, ноль если выдавать было нечего.
    * «Отменено» в выручку не входит.
    """
    shift_list = [s for s in shifts if s is not None]
    ids = [s.id for s in shift_list]
    empty = {
        "shifts": shift_list,
        "issued": 0,
        "revenue": Decimal("0.00"),
        "addon_revenue": Decimal("0.00"),
        "avg": Decimal("0.00"),
        "cancelled": 0,
        "items": [],
        "categories": [],
        "addons": [],
    }
    if not ids:
        return empty

    orders = Order.objects.filter(shift_id__in=ids).exclude(status=Order.Status.NEW)
    issued = orders.filter(status__in=ISSUED_STATUSES).count()
    cancelled = orders.filter(status=Order.Status.CANCELLED).count()
    paid = orders.filter(is_paid=True).exclude(status=Order.Status.CANCELLED)
    revenue = paid.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
    avg = (revenue / issued) if issued else Decimal("0.00")
    paid_ids = set(paid.values_list("id", flat=True))

    lines = (
        OrderLine.objects.filter(order__shift_id__in=ids)
        .exclude(order__status__in=[Order.Status.NEW, Order.Status.CANCELLED])
        .select_related("product__category", "order")
        .prefetch_related("modifiers__modifier")
    )
    item_qty: dict[str, int] = {}
    item_rev: dict[str, Decimal] = {}
    cat_qty: dict[str, int] = {}
    cat_rev: dict[str, Decimal] = {}
    cat_color: dict[str, str] = {}
    addon_qty: dict[str, int] = {}
    addon_revenue = Decimal("0.00")

    for line in lines:
        name = line.name_snapshot
        qty = line.quantity
        item_qty[name] = item_qty.get(name, 0) + qty
        category = getattr(line.product, "category", None)
        cat_name = category.name if category is not None else "Без категории"
        cat_qty[cat_name] = cat_qty.get(cat_name, 0) + qty
        cat_color.setdefault(cat_name, getattr(category, "color", None) or "#2e78d9")
        if line.order_id in paid_ids:
            subtotal = line.subtotal()
            item_rev[name] = item_rev.get(name, Decimal("0.00")) + subtotal
            cat_rev[cat_name] = cat_rev.get(cat_name, Decimal("0.00")) + subtotal
            for modifier in line.modifiers.all():
                addon_revenue += modifier.price_delta_snapshot * qty
        for modifier in line.modifiers.all():
            is_default = bool(getattr(modifier.modifier, "is_default", False))
            if modifier.price_delta_snapshot == 0 and is_default:
                continue
            addon_qty[modifier.name_snapshot] = (
                addon_qty.get(modifier.name_snapshot, 0) + qty
            )

    items = [
        {"name": name, "qty": qty, "revenue": item_rev.get(name, Decimal("0.00"))}
        for name, qty in item_qty.items()
    ]
    items.sort(key=lambda row: (row["revenue"], row["qty"]), reverse=True)
    max_qty = max((row["qty"] for row in items), default=0) or 1
    for row in items:
        row["width"] = round(100 * row["qty"] / max_qty)

    categories = [
        {
            "name": name,
            "qty": qty,
            "revenue": cat_rev.get(name, Decimal("0.00")),
            "color": cat_color.get(name, "#2e78d9"),
        }
        for name, qty in cat_qty.items()
    ]
    categories.sort(key=lambda row: (row["revenue"], row["qty"]), reverse=True)
    whole = sum((row["revenue"] for row in categories), Decimal("0.00"))
    whole_qty = sum(row["qty"] for row in categories) or 1
    for row in categories:
        if whole > 0:
            row["share"] = int(round(100 * row["revenue"] / whole))
        else:
            row["share"] = int(round(100 * row["qty"] / whole_qty))

    addons = [
        {"name": name, "qty": qty}
        for name, qty in addon_qty.items()
    ]
    addons.sort(key=lambda row: row["qty"], reverse=True)

    return {
        "shifts": shift_list,
        "issued": issued,
        "revenue": revenue,
        "addon_revenue": addon_revenue,
        "avg": avg,
        "cancelled": cancelled,
        "items": items[:8],
        "categories": categories,
        "addons": addons[:8],
    }


def current_business_date():
    """Дата открытой смены либо ``None``, если смену ещё не открыли."""
    shift = get_open_shift()
    return shift.business_date if shift else None


def _attach_open_shift(order: Order) -> None:
    """Привязать заказ к открытой смене, если она есть и слот ещё пуст."""
    if order.shift_id is not None:
        return
    shift = get_open_shift()
    if shift is not None:
        order.shift = shift


@transaction.atomic
def create_order(
    *,
    created_by=None,
    fulfilment: str = Order.Fulfilment.HERE,
    guest_name: str = "",
) -> Order:
    """Создать новый пустой заказ в статусе :attr:`Order.Status.NEW`."""
    return Order.objects.create(
        created_by=created_by,
        fulfilment=fulfilment,
        guest_name=guest_name,
    )


@transaction.atomic
def add_line(
    order: Order,
    product: Product,
    quantity: int = 1,
    modifier_ids: Iterable[int] | None = None,
) -> OrderLine:
    """Добавить товар в ``order`` вместе с опционально выбранными модификаторами."""
    if quantity < 1:
        raise ValueError("Количество должно быть >= 1.")

    line = OrderLine.objects.create(
        order=order,
        product=product,
        name_snapshot=product.name,
        unit_price=product.price,
        quantity=quantity,
    )

    if modifier_ids:
        modifiers = list(
            Modifier.objects.filter(id__in=modifier_ids, is_active=True)
            .select_related("group")
        )
        _validate_modifier_choice(product, modifiers)
        for modifier in modifiers:
            OrderLineModifier.objects.create(
                line=line,
                modifier=modifier,
                name_snapshot=modifier.name,
                price_delta_snapshot=modifier.price_delta,
            )

    order.recalc_total()
    return line


def _validate_modifier_choice(product: Product, modifiers: list[Modifier]) -> None:
    """Проверить, что вызывающий соблюдает правила single-choice-групп и allow-list товара.

    Из single-choice-группы можно взять не более одной опции; группы, не
    привязанные к ``product``, отклоняются.
    """
    allowed_groups = set(product.modifier_groups.values_list("id", flat=True))
    per_group: dict[int, int] = {}
    for m in modifiers:
        if m.group_id not in allowed_groups:
            raise ValueError(
                f"Модификатор «{m.name}» недоступен для «{product.name}»."
            )
        per_group[m.group_id] = per_group.get(m.group_id, 0) + 1

    single_groups = set(
        ModifierGroup.objects.filter(
            id__in=per_group, selection_mode=ModifierGroup.SELECTION_SINGLE
        ).values_list("id", flat=True)
    )
    for group_id, count in per_group.items():
        if group_id in single_groups and count > 1:
            raise ValueError("Нельзя выбрать несколько опций в группе одного выбора.")

    missing = (
        product.modifier_groups.filter(is_required=True)
        .exclude(id__in=per_group)
        .order_by("order", "name")
    )
    for group in missing:
        raise ValueError(f"Выберите опцию в группе «{group.name}».")


@transaction.atomic
def update_line(
    line: OrderLine,
    *,
    modifier_ids: Iterable[int] | None = None,
    note: str | None = None,
) -> OrderLine:
    """Заменить допы и заметку позиции и пересчитать сумму заказа."""
    if modifier_ids is not None:
        modifiers = list(
            Modifier.objects.filter(id__in=list(modifier_ids), is_active=True)
            .select_related("group")
        )
        _validate_modifier_choice(line.product, modifiers)
        line.modifiers.all().delete()
        for modifier in modifiers:
            OrderLineModifier.objects.create(
                line=line,
                modifier=modifier,
                name_snapshot=modifier.name,
                price_delta_snapshot=modifier.price_delta,
            )
    if note is not None:
        line.note = note.strip()
        line.save(update_fields=["note"])
    line.order.recalc_total()
    return line


@transaction.atomic
def change_line_quantity(line: OrderLine, quantity: int) -> None:
    """Задать ``line.quantity`` (0 удаляет позицию) и пересчитать заказ."""
    if quantity <= 0:
        order = line.order
        line.delete()
    else:
        line.quantity = quantity
        line.save(update_fields=["quantity"])
        order = line.order
    order.recalc_total()


@transaction.atomic
def remove_line(line: OrderLine) -> None:
    """Удалить позицию из заказа и пересчитать итоговую сумму."""
    order = line.order
    line.delete()
    order.recalc_total()


@transaction.atomic
def update_order_meta(
    order: Order,
    *,
    guest_name: str | None = None,
    comment: str | None = None,
    fulfilment: str | None = None,
) -> Order:
    """Обновить лёгкую метаинформацию заказа (имя гостя, комментарий, «в зале/с собой»)."""
    changed = []
    if guest_name is not None:
        order.guest_name = guest_name
        changed.append("guest_name")
    if comment is not None:
        order.comment = comment
        changed.append("comment")
    if fulfilment is not None and fulfilment in dict(Order.Fulfilment.choices):
        order.fulfilment = fulfilment
        changed.append("fulfilment")
    if changed:
        order.save(update_fields=changed)
    return order


@transaction.atomic
def pay_order(order: Order) -> Order:
    """Отметить ``order`` оплаченным.

    Черновик при этом уходит в очередь («не готово»). Заказ, который
    бариста уже двигал (готово / отменено / не готово), статус готовности
    не теряет — гаснет только плашка «не оплачено».
    """
    if not order.lines.exists():
        raise ValueError("Нельзя оплатить пустой заказ.")
    if order.is_paid:
        return order
    order.is_paid = True
    if order.status == Order.Status.NEW:
        order.status = Order.Status.IN_PROGRESS
    order.paid_at = timezone.now()
    _attach_open_shift(order)
    order.save(update_fields=["is_paid", "status", "paid_at", "shift"])
    return order


@transaction.atomic
def enqueue_order(order: Order) -> Order:
    """Отправить черновик баристе, не отмечая оплату.

    Заказ появляется в левой очереди как «Не готово» и «не оплачено».
    Если открыта смена, заказ привязывается к её дате. Уже оплаченный
    заказ не трогаем.
    """
    if not order.lines.exists():
        raise ValueError("Нельзя отправить пустой заказ.")
    if order.is_paid:
        return order
    order.status = Order.Status.IN_PROGRESS
    _attach_open_shift(order)
    order.save(update_fields=["status", "shift"])
    return order


_BARISTA_CYCLE = (
    Order.Status.IN_PROGRESS,
    Order.Status.READY,
    Order.Status.CANCELLED,
)


@transaction.atomic
def set_barista_status(order: Order, status: str) -> Order:
    """Поставить готовность сразу: не готово, готово или отменено.

    Оплату не меняет. Те же три значения, что у :func:`cycle_barista_status`.
    """
    if status not in _BARISTA_CYCLE:
        raise ValueError("Неизвестный статус очереди.")
    order.status = status
    if order.status == Order.Status.READY:
        order.ready_at = timezone.now()
    elif order.status == Order.Status.IN_PROGRESS:
        order.ready_at = None
    order.save(update_fields=["status", "ready_at"])
    return order


@transaction.atomic
def cycle_barista_status(order: Order) -> Order:
    """Прокрутить статус очереди: не готово → готово → отменено → не готово."""
    try:
        index = _BARISTA_CYCLE.index(order.status)
    except ValueError:
        index = -1
    return set_barista_status(order, _BARISTA_CYCLE[(index + 1) % len(_BARISTA_CYCLE)])


@transaction.atomic
def mark_ready(order: Order) -> Order:
    """Перевести ``order`` в статус :attr:`Order.Status.READY`."""
    order.status = Order.Status.READY
    order.ready_at = timezone.now()
    order.save(update_fields=["status", "ready_at"])
    return order


@transaction.atomic
def mark_all_ready() -> int:
    """Перевести все заказы со статусом ``IN_PROGRESS`` в ``READY``.

    Возвращает количество обновлённых заказов. Используется кнопкой
    «Все готовы» на экране выдачи.
    """
    orders = list(Order.objects.filter(status=Order.Status.IN_PROGRESS))
    now = timezone.now()
    for order in orders:
        order.status = Order.Status.READY
        order.ready_at = now
    Order.objects.bulk_update(orders, ["status", "ready_at"])
    return len(orders)


@transaction.atomic
def hand_off(order: Order) -> Order:
    """Отметить ``order`` как выданный гостю."""
    if order.status == Order.Status.NEW:
        raise ValueError("Заказ ещё не оплачен.")
    order.status = Order.Status.HANDED_OFF
    order.handed_off_at = timezone.now()
    order.save(update_fields=["status", "handed_off_at"])
    return order


@transaction.atomic
def cancel_order(order: Order) -> Order:
    """Отменить заказ (имеет смысл только до выдачи)."""
    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status"])
    return order


def barista_queue(*, limit_cancelled: int = 8) -> list[Order]:
    """Заказы для левой колонки кассы.

    Сначала «не готово», затем «готово», затем несколько последних
    «отменено». Черновики и уже отданные заказы сюда не попадают.
    Открытая смена, если она есть, ограничивает выборку: заказы без смены
    тоже видны, чтобы касса работала до экрана открытия смены.
    """
    rank = Case(
        When(status=Order.Status.IN_PROGRESS, then=0),
        When(status=Order.Status.READY, then=1),
        When(status=Order.Status.CANCELLED, then=2),
        default=9,
        output_field=IntegerField(),
    )
    base = Order.objects.filter(
        status__in=[
            Order.Status.IN_PROGRESS,
            Order.Status.READY,
            Order.Status.CANCELLED,
        ]
    )
    shift = get_open_shift()
    if shift is not None:
        base = base.filter(Q(shift=shift) | Q(shift__isnull=True))

    active = list(
        base.exclude(status=Order.Status.CANCELLED)
        .annotate(_rank=rank)
        .prefetch_related("lines__modifiers__modifier")
        .order_by("_rank", "id")
    )
    cancelled = list(
        base.filter(status=Order.Status.CANCELLED)
        .prefetch_related("lines__modifiers__modifier")
        .order_by("-id")[:limit_cancelled]
    )
    cancelled.reverse()
    return active + cancelled


def totals_for_today() -> dict[str, Decimal | int]:
    """Вернуть текущие итоги за сегодня для виджета в верхней панели.

    Считает по календарной дате ``created_at``. Бизнес-дата смены для
    отчётов подключится вместе с экраном закрытия смены.
    """
    today = timezone.localdate()
    qs = Order.objects.filter(created_at__date=today, is_paid=True)
    revenue = sum((o.total_amount for o in qs), Decimal("0.00"))
    return {"revenue": revenue, "orders": qs.count()}
