"""Модели жизненного цикла заказа.

:class:`Order` проходит по следующим статусам (см. :attr:`Order.Status`)::

    NEW -> IN_PROGRESS -> READY -> HANDED_OFF

Типовая смена выглядит так:

1. Кассир собирает :class:`Order` из позиций :class:`OrderLine` и,
   опционально, привязывает к каждой позиции :class:`OrderLineModifier`.
2. «В очередь» ставит заказ в работу (``IN_PROGRESS``), не меняя
   :attr:`Order.is_paid`. На карточке это «не оплачено» плюс «не готово».
   «Оплатить» ставит :attr:`Order.is_paid` и тоже отправляет черновик
   в очередь, но плашка «не оплачено» не показывается.
3. Готовность крутится отдельно: не готово → готово → отменено.
   Оплата её не сбрасывает. Кассир выдаёт заказ
   (:attr:`Order.Status.HANDED_OFF`).
4. У каждой позиции есть флаг «отдали». Если отмечены все и заказ
   оплачен, через 5 секунд он сам становится «Готово» — это же время
   выдачи. Оплаченное «Готово» и любая «Отмена» ещё 13 секунд остаются
   в основной очереди, затем уходят в «Готовые» или «Отмена».
5. В конце смены :func:`apps.orders.services.close_day` фиксирует итоги в
   :class:`apps.analytics.models.DailySummary`.
"""

from __future__ import annotations

import string
from datetime import datetime, time
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


def shift_relative_datetime(shift, event_at: datetime | None) -> datetime | None:
    """Вернуть момент события на часах смены.

    Формула: вписанное :attr:`Shift.start_time` плюс
    ``event_at - shift.opened_at``. Оба штампа сняты с часов сервера,
    поэтому в результат входит только их разность. Абсолютное показание
    (ноутбук не идёт, пока выключен) никуда не подставляется.
    """
    if (
        shift is None
        or event_at is None
        or shift.opened_at is None
        or shift.start_time is None
        or shift.business_date is None
    ):
        return None
    opened = shift.opened_at
    event = event_at
    if timezone.is_aware(opened) != timezone.is_aware(event):
        zone = timezone.get_current_timezone()
        if timezone.is_aware(opened):
            opened = timezone.make_naive(opened, zone)
        if timezone.is_aware(event):
            event = timezone.make_naive(event, zone)
    elapsed = event - opened
    return datetime.combine(shift.business_date, shift.start_time) + elapsed


def format_shift_clock(moment: datetime | None) -> str:
    """``ЧЧ:ММ`` без локали. Пустая строка, если момента нет."""
    if moment is None:
        return ""
    return f"{moment.hour:02d}:{moment.minute:02d}"


class Shift(models.Model):
    """Рабочая смена с датой и началом, которые вписывает кассир.

    Дата и :attr:`start_time` вводятся на экране «Смена» и больше
    ниоткуда не подставляются. :attr:`opened_at` запоминает часы сервера
    в момент открытия только как ноль отсчёта: время заказа — это
    начало смены плюс прошедшее с этого нуля (см.
    :func:`shift_relative_datetime`). Само :attr:`opened_at` нигде не
    показывается. :attr:`closed_at` по-прежнему не заполняется: ноутбук
    может врать в абсолютных показаниях. Закрытие ставит :attr:`is_open`
    в ``False`` и запоминает :attr:`closed_by`. Незавершённые заказы
    при этом не отменяются — они остаются историей этой смены.
    """

    business_date = models.DateField("Дата смены", db_index=True)
    start_time = models.TimeField(
        "Начало смены",
        default=time(19, 30),
        help_text=(
            "Время, которое кассир вписал при открытии. "
            "К нему прибавляется прошедшее с открытия смены."
        ),
    )
    is_open = models.BooleanField("Открыта", default=True, db_index=True)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shifts_opened",
        verbose_name="Открыл",
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shifts_closed",
        verbose_name="Закрыл",
    )
    cashier_name = models.CharField(
        "Кассир",
        max_length=100,
        blank=True,
        help_text="Имя на кассе, как его вписали при открытии смены.",
    )
    opened_at = models.DateTimeField(
        "Открыта в",
        null=True,
        blank=True,
        help_text=(
            "Часы сервера в момент открытия. Для времени заказов берётся "
            "только разница с этим моментом, само значение не показывается."
        ),
    )
    closed_at = models.DateTimeField("Закрыта в", null=True, blank=True)

    class Meta:
        verbose_name = "Смена"
        verbose_name_plural = "Смены"
        ordering = ("-business_date", "-id")

    def __str__(self) -> str:  # pragma: no cover - trivial
        state = "открыта" if self.is_open else "закрыта"
        return f"Смена {self.business_date:%d.%m.%Y} ({state})"


def _generate_short_code() -> str:
    """Вернуть короткий человекочитаемый идентификатор вида ``B7-42``.

    Мы намеренно исключаем символы, которые легко перепутать на телефоне
    или на распечатанном чеке (``0/O``, ``1/I``).
    """
    import secrets

    alphabet = "".join(c for c in string.ascii_uppercase + string.digits
                       if c not in "OI01")
    return f"{secrets.choice(alphabet)}{secrets.choice(alphabet)}-{secrets.randbelow(90) + 10}"


class Order(models.Model):
    """Заказ одного гостя.

    Вьюха очереди (:mod:`apps.orders.views`) фильтрует записи по
    :attr:`is_paid` / :attr:`status`; приложение аналитики агрегирует по
    :attr:`created_at` и :attr:`total_amount`.
    """

    class Status(models.TextChoices):
        NEW = "new", "Черновик"
        IN_PROGRESS = "in_progress", "В работе"
        READY = "ready", "Готов"
        HANDED_OFF = "handed_off", "Отдан"
        CANCELLED = "cancelled", "Отменён"

    class Fulfilment(models.TextChoices):
        HERE = "here", "В зале"
        TO_GO = "to_go", "С собой"

    short_code = models.CharField(
        "Номер",
        max_length=16,
        unique=True,
        default=_generate_short_code,
        db_index=True,
    )
    guest_name = models.CharField("Имя гостя", max_length=100, blank=True)
    comment = models.TextField("Комментарий", blank=True)
    status = models.CharField(
        "Статус", max_length=16, choices=Status.choices, default=Status.NEW
    )
    fulfilment = models.CharField(
        "Формат",
        max_length=8,
        choices=Fulfilment.choices,
        default=Fulfilment.HERE,
    )
    is_paid = models.BooleanField("Оплачен", default=False)
    total_amount = models.DecimalField(
        "Итого, ₽",
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders_created",
        verbose_name="Кассир",
    )
    shift = models.ForeignKey(
        Shift,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        verbose_name="Смена",
        help_text="Заполняется при оплате или отправке в очередь, если смена открыта.",
    )
    created_at = models.DateTimeField("Создан", default=timezone.now, db_index=True)
    paid_at = models.DateTimeField("Оплачен в", null=True, blank=True)
    ready_at = models.DateTimeField("Готов в", null=True, blank=True)
    handed_off_at = models.DateTimeField("Отдан в", null=True, blank=True)
    cancelled_at = models.DateTimeField("Отменён в", null=True, blank=True)
    auto_ready_at = models.DateTimeField(
        "Автоготово с",
        null=True,
        blank=True,
        help_text=(
            "Момент, когда все позиции отмечены «отдали» и заказ оплачен. "
            "Через 5 секунд статус становится «Готово», если галочку сняли "
            "или оплату убрали раньше."
        ),
    )
    main_queue_until = models.DateTimeField(
        "В основной очереди до",
        null=True,
        blank=True,
        help_text=(
            "Оплаченное «Готово» и «Отменено» остаются в основной очереди "
            "до этого момента (13 секунд), затем видны только в «Готовые» "
            "или «Отмена»."
        ),
    )

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ("-created_at",)

    def recalc_total(self) -> Decimal:
        """Пересчитать :attr:`total_amount` по текущим позициям и модификаторам.

        Сохраняет и возвращает новую сумму. Вызывается автоматически из
        :func:`apps.orders.services` при любом изменении позиций или
        модификаторов.
        """
        cache = getattr(self, "_prefetched_objects_cache", None)
        if cache is not None:
            cache.pop("lines", None)
        total = Decimal("0.00")
        for line in self.lines.all():
            total += line.subtotal()
        self.total_amount = total
        self.save(update_fields=["total_amount"])
        return total

    def barista_label(self) -> str:
        """Короткая подпись готовности для очереди баристы.

        Оплата сюда не входит: её показывает :meth:`unpaid_label`.
        """
        return {
            self.Status.IN_PROGRESS: "Не готово",
            self.Status.READY: "Готово",
            self.Status.CANCELLED: "Отменено",
        }.get(self.status, self.get_status_display())

    def unpaid_label(self) -> str:
        """Плашка оплаты. Пустая строка, если заказ уже оплачен."""
        if self.is_paid:
            return ""
        return "не оплачено"

    def is_takeaway(self) -> bool:
        """Заказ «на вынос». По умолчанию заказ «здесь»."""
        return self.fulfilment == self.Fulfilment.TO_GO

    def place_mark(self) -> str:
        """Знак на карточке очереди: 🏃 на вынос, ☕ здесь."""
        return "🏃" if self.is_takeaway() else "☕"

    def place_title(self) -> str:
        """Подсказка знака: «на вынос» или «здесь»."""
        return "на вынос" if self.is_takeaway() else "здесь"

    def is_active(self) -> bool:
        """Вернуть ``True``, если заказ должен показываться в активной очереди."""
        return self.status in {
            self.Status.NEW,
            self.Status.IN_PROGRESS,
            self.Status.READY,
        }

    def waiting_seconds(self) -> int:
        """Сколько секунд прошло с оплаты заказа; используется, чтобы поторопить смену."""
        if not self.paid_at:
            return 0
        end = self.handed_off_at or self.ready_at or timezone.now()
        return int((end - self.paid_at).total_seconds())

    def payment_moment(self) -> datetime | None:
        """Момент оплаты на часах смены, либо ``None``.

        Это :attr:`Shift.start_time` плюс время от :attr:`Shift.opened_at`
        до :attr:`paid_at`. Абсолютные часы ноутбука в результат не входят.
        """
        return shift_relative_datetime(self.shift, self.paid_at)

    def payment_clock(self) -> str:
        """Оплата как ``ЧЧ:ММ`` на часах смены. Пустая строка, если времени нет."""
        return format_shift_clock(self.payment_moment())

    def handout_moment(self) -> datetime | None:
        """Момент выдачи: заказ перевели в «Готово» (выдан) или «Отдан».

        Берётся :attr:`ready_at`. Если его нет, а статус уже «Отдан»,
        используется :attr:`handed_off_at`. Дальше та же формула, что у
        :meth:`payment_moment`.
        """
        stamp = self.ready_at
        if stamp is None and self.status == self.Status.HANDED_OFF:
            stamp = self.handed_off_at
        return shift_relative_datetime(self.shift, stamp)

    def handout_clock(self) -> str:
        """Выдача как ``ЧЧ:ММ`` на часах смены. Пустая строка, если заказ ещё не выдан."""
        return format_shift_clock(self.handout_moment())

    def __str__(self) -> str:  # pragma: no cover - trivial
        who = self.guest_name or "—"
        return f"{self.short_code} · {who}"


class OrderLine(models.Model):
    """Одна позиция :class:`~apps.catalog.models.Product` внутри :class:`Order`."""

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="lines", verbose_name="Заказ"
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Товар",
    )
    name_snapshot = models.CharField("Название (снимок)", max_length=200)
    unit_price = models.DecimalField(
        "Цена за единицу, ₽", max_digits=8, decimal_places=2
    )
    quantity = models.PositiveIntegerField("Количество", default=1)
    note = models.CharField("Заметка к позиции", max_length=200, blank=True)
    handed_out = models.BooleanField(
        "Отдали",
        default=False,
        help_text="Позицию уже отдали гостю. На карточке очереди это галочка.",
    )

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"

    def subtotal(self) -> Decimal:
        """Вернуть сумму по позиции с учётом ценовых дельт модификаторов."""
        modifiers_total = sum(
            (m.price_delta_snapshot for m in self.modifiers.all()),
            Decimal("0.00"),
        )
        return (self.unit_price + modifiers_total) * self.quantity

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.name_snapshot} × {self.quantity}"


class OrderLineModifier(models.Model):
    """Один :class:`~apps.catalog.models.Modifier`, прикреплённый к позиции."""

    line = models.ForeignKey(
        OrderLine,
        on_delete=models.CASCADE,
        related_name="modifiers",
        verbose_name="Позиция",
    )
    modifier = models.ForeignKey(
        "catalog.Modifier",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Модификатор",
    )
    name_snapshot = models.CharField("Название (снимок)", max_length=200)
    price_delta_snapshot = models.DecimalField(
        "Изменение цены (снимок), ₽",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    class Meta:
        verbose_name = "Модификатор позиции"
        verbose_name_plural = "Модификаторы позиции"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name_snapshot
