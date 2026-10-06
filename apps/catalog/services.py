"""Бизнес-помощники приложения catalog.

Вынесены отдельно от :mod:`views`, чтобы их можно было покрывать юнит-тестами
и переиспользовать из CLI или других приложений, не проходя через HTTP-слой.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from .models import Category, Modifier, ModifierGroup, Product


def _option(group, name, price, order, *, default=False) -> Modifier:
    return Modifier(
        group=group,
        name=name,
        price_delta=Decimal(price),
        is_default=default,
        order=order,
    )


def seed_demo_menu() -> None:
    """Заполнить БД меню «6ки» с платными допами.

    Вызывается management-командой
    :mod:`apps.catalog.management.commands.seed_demo`, а также функцией
    :func:`apps.pos.bootstrap.ensure_bootstrapped` при первом запуске,
    когда каталог пуст. Повторный запуск ничего не меняет.
    """

    if Category.objects.exists():
        return

    with transaction.atomic():
        classics = Category.objects.create(name="Классика", slug="klassika", order=1, color="#2e78d9")
        teas = Category.objects.create(name="Чаи", slug="chai", order=2, color="#38a866")
        seasonal = Category.objects.create(
            name="Сезонные напитки", slug="sezon", order=3, color="#f2b838"
        )
        food = Category.objects.create(name="Еда", slug="eda", order=4, color="#c74747")

        milk = ModifierGroup.objects.create(
            name="Молоко", slug="milk",
            selection_mode=ModifierGroup.SELECTION_SINGLE, is_required=False, order=1,
        )
        size = ModifierGroup.objects.create(
            name="Размер", slug="size",
            selection_mode=ModifierGroup.SELECTION_SINGLE, is_required=False, order=2,
        )
        syrup = ModifierGroup.objects.create(
            name="Сиропы", slug="syrups",
            selection_mode=ModifierGroup.SELECTION_MULTI, is_required=False, order=3,
        )
        extra = ModifierGroup.objects.create(
            name="Экстра", slug="extra",
            selection_mode=ModifierGroup.SELECTION_MULTI, is_required=False, order=4,
        )
        Modifier.objects.bulk_create(
            [
                _option(milk, "обычное", "0", 1, default=True),
                _option(milk, "овсяное", "30", 2),
                _option(milk, "миндальное", "40", 3),
                _option(milk, "безлактозное", "30", 4),
                _option(size, "обычный", "0", 1, default=True),
                _option(size, "большой", "40", 2),
                _option(syrup, "ваниль", "20", 1),
                _option(syrup, "карамель", "20", 2),
                _option(syrup, "лесной орех", "25", 3),
                _option(extra, "экстра шот", "50", 1),
                _option(extra, "мёд", "20", 2),
            ]
        )

        drink_groups = [milk, size, syrup, extra]
        tea_groups = [size, extra]

        def add(name, price, category, order, groups=None) -> None:
            product = Product.objects.create(
                name=name, price=Decimal(price), category=category, order=order
            )
            if groups:
                product.modifier_groups.set(groups)

        add("Латте", "220", classics, 1, drink_groups)
        add("Капучино", "210", classics, 2, drink_groups)
        add("Американо", "170", classics, 3, drink_groups)
        add("Эспрессо", "150", classics, 4)
        add("Чай облепиховый", "180", teas, 1, tea_groups)
        add("Чай жмых", "160", teas, 2)
        add("Чай листовой", "150", teas, 3)
        add("Матча латте", "250", teas, 4, drink_groups)
        add("Айс-латте", "280", seasonal, 1, drink_groups)
        add("Раф тыквенный", "290", seasonal, 2, drink_groups)
        add("Глинтвейн", "260", seasonal, 3)
        add("Круассан", "120", food, 1)
        add("Шоколадный маффин", "160", food, 2)
