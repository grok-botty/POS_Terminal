"""Бизнес-логика приложения orders.

Все мутации :class:`~apps.orders.models.Order` идут через этот модуль, чтобы
шаблоны и вьюхи оставались тонкими. Каждая функция транзакционна и безопасна
для вызова из shell.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from django.db import transaction
from django.db.models import Case, IntegerField, Q, When
from django.utils import timezone

from apps.catalog.models import Modifier, ModifierGroup, Product

from .models import Order, OrderLine, OrderLineModifier, Shift


def get_open_shift() -> Shift | None:
    """Вернуть открытую смену или ``None``.

    Бизнес-дата берётся только отсюда. Если смены нет, вызывающий не
    подставляет системную дату — экран открытия смены появится позже.
    """
    return Shift.objects.filter(is_open=True).order_by("-id").first()


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
    """Отметить ``order`` оплаченным и отправить в кухонную очередь."""
    if not order.lines.exists():
        raise ValueError("Нельзя оплатить пустой заказ.")
    if order.is_paid:
        return order
    order.is_paid = True
    order.status = Order.Status.IN_PROGRESS
    order.paid_at = timezone.now()
    _attach_open_shift(order)
    order.save(update_fields=["is_paid", "status", "paid_at", "shift"])
    return order


@transaction.atomic
def enqueue_order(order: Order) -> Order:
    """Отправить черновик баристе, не отмечая оплату.

    Заказ появляется в левой очереди со статусом «Не готово». Если открыта
    смена, заказ привязывается к её дате.
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
def cycle_barista_status(order: Order) -> Order:
    """Прокрутить статус очереди: не готово → готово → отменено → не готово."""
    try:
        index = _BARISTA_CYCLE.index(order.status)
    except ValueError:
        index = -1
    order.status = _BARISTA_CYCLE[(index + 1) % len(_BARISTA_CYCLE)]
    if order.status == Order.Status.READY:
        order.ready_at = timezone.now()
    elif order.status == Order.Status.IN_PROGRESS:
        order.ready_at = None
    order.save(update_fields=["status", "ready_at"])
    return order


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
