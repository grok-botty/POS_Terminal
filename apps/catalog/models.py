"""Домен меню: категории, товары и модификаторы товаров.

Каталог намеренно устроен просто:

* :class:`Category` группирует товары (например, «Напитки», «Десерты»).
* :class:`Product` — продаваемая позиция меню.
* :class:`ModifierGroup` описывает набор опций, которые можно прикрепить к
  товару (например, «Сироп», «Молоко»). Группы бывают с одиночным выбором
  (выбрать одно молоко) и с множественным (добавить несколько сиропов).
* :class:`Modifier` — одна опция внутри группы со своей ценовой дельтой.

Товары подписываются на нужные группы модификаторов: у эспрессо может быть
опция «Молоко», а у фильтр-кофе — нет.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    """Логическая группировка товаров (вкладка на экране кассы)."""

    name = models.CharField("Название", max_length=100)
    slug = models.SlugField("Slug", max_length=100, unique=True)
    order = models.IntegerField("Порядок", default=0)
    color = models.CharField(
        "Цвет плитки",
        max_length=16,
        default="#f2b134",
        help_text="HEX-цвет для оформления вкладки, например #f2b134.",
    )
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ("order", "name")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True) or "category"
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


class ModifierGroup(models.Model):
    """Набор опций :class:`Modifier`, которые кассир может прикрепить к заказу.

    Группа со значением :attr:`selection_mode` равным
    :attr:`SELECTION_SINGLE` ведёт себя как радиогруппа (выбор одного
    молока); группа с :attr:`SELECTION_MULTI` — как список чекбоксов
    (можно добавить сколько угодно сиропов).
    """

    SELECTION_SINGLE = "single"
    SELECTION_MULTI = "multi"
    SELECTION_CHOICES = (
        (SELECTION_SINGLE, "Один вариант"),
        (SELECTION_MULTI, "Несколько вариантов"),
    )

    name = models.CharField("Название", max_length=100)
    slug = models.SlugField("Slug", max_length=100, unique=True)
    selection_mode = models.CharField(
        "Режим выбора",
        max_length=10,
        choices=SELECTION_CHOICES,
        default=SELECTION_MULTI,
    )
    is_required = models.BooleanField(
        "Обязателен",
        default=False,
        help_text="Кассир обязан выбрать хотя бы одну опцию.",
    )
    order = models.IntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Группа модификаторов"
        verbose_name_plural = "Группы модификаторов"
        ordering = ("order", "name")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True) or "group"
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


class Modifier(models.Model):
    """Одна выбираемая опция внутри :class:`ModifierGroup`."""

    group = models.ForeignKey(
        ModifierGroup,
        on_delete=models.CASCADE,
        related_name="options",
        verbose_name="Группа",
    )
    name = models.CharField("Название", max_length=100)
    price_delta = models.DecimalField(
        "Изменение цены, ₽",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Может быть отрицательным (скидка).",
    )
    is_active = models.BooleanField("Активен", default=True)
    order = models.IntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Модификатор"
        verbose_name_plural = "Модификаторы"
        ordering = ("group", "order", "name")

    def __str__(self) -> str:  # pragma: no cover - trivial
        sign = "+" if self.price_delta >= 0 else ""
        return f"{self.name} ({sign}{self.price_delta} ₽)"


class Product(models.Model):
    """Позиция меню, предлагаемая гостям."""

    name = models.CharField("Название", max_length=200)
    price = models.DecimalField(
        "Цена, ₽", max_digits=8, decimal_places=2, default=Decimal("0.00")
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="products",
        verbose_name="Категория",
    )
    modifier_groups = models.ManyToManyField(
        ModifierGroup,
        blank=True,
        related_name="products",
        verbose_name="Группы модификаторов",
        help_text="Какие опции показывать при добавлении в заказ.",
    )
    is_active = models.BooleanField("Активен", default=True)
    order = models.IntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ("category__order", "order", "name")

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.name} — {self.price} ₽"
