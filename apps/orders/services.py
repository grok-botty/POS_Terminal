"""Бизнес-логика приложения orders.

Все мутации :class:`~apps.orders.models.Order` идут через этот модуль, чтобы
шаблоны и вьюхи оставались тонкими. Каждая функция транзакционна и безопасна
для вызова из shell.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Modifier, ModifierGroup, Product

from .models import Order, OrderLine, OrderLineModifier


@transaction.atomic
def create_order(*, created_by=None, fulfilment: str = Order.Fulfilment.HERE) -> Order:
    """Создать новый пустой заказ в статусе :attr:`Order.Status.NEW`."""
    return Order.objects.create(created_by=created_by, fulfilment=fulfilment)


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
    order.save(update_fields=["is_paid", "status", "paid_at"])
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


def totals_for_today() -> dict[str, Decimal | int]:
    """Вернуть текущие итоги за сегодня для виджета в верхней панели."""
    today = timezone.localdate()
    qs = Order.objects.filter(created_at__date=today, is_paid=True)
    revenue = sum((o.total_amount for o in qs), Decimal("0.00"))
    return {"revenue": revenue, "orders": qs.count()}
