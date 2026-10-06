"""Модели жизненного цикла заказа.

:class:`Order` проходит по следующим статусам (см. :attr:`Order.Status`)::

    NEW -> IN_PROGRESS -> READY -> HANDED_OFF

Типовая смена выглядит так:

1. Кассир собирает :class:`Order` из позиций :class:`OrderLine` и,
   опционально, привязывает к каждой позиции :class:`OrderLineModifier`.
2. Когда гость оплачивает заказ, :attr:`Order.is_paid` становится
   ``True``, а сам заказ попадает в кухонную очередь (``IN_PROGRESS``).
3. Бариста помечает заказ :attr:`Order.Status.READY`. Кассир выдаёт его
   (:attr:`Order.Status.HANDED_OFF`).
4. В конце смены :func:`apps.orders.services.close_day` фиксирует итоги в
   :class:`apps.analytics.models.DailySummary`.
"""

from __future__ import annotations

import string
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class Shift(models.Model):
    """Рабочая смена с бизнес-датой, которую задаёт кассир, а не часы ноутбука.

    Экран открытия и закрытия смены (ручная дата) появится отдельным
    проходом. Пока смена может быть создана из админки или shell: если
    есть открытая запись, новые заказы привязываются к ней через
    :attr:`Order.shift`, и шапка кассы показывает её :attr:`business_date`.
    """

    business_date = models.DateField("Дата смены", db_index=True)
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
    opened_at = models.DateTimeField("Открыта в", null=True, blank=True)
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
        """Короткая подпись статуса для очереди баристы."""
        return {
            self.Status.IN_PROGRESS: "Не готово",
            self.Status.READY: "Готово",
            self.Status.CANCELLED: "Отменено",
        }.get(self.status, self.get_status_display())

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
