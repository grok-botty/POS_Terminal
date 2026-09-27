"""Business helpers for the catalog app.

Kept separate from :mod:`views` so they can be unit-tested and reused from the
CLI or from other apps without going through the HTTP layer.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from django.db import transaction

from .models import Category, Modifier, ModifierGroup, Product


def seed_demo_menu() -> None:
    """Populate the database with a small realistic menu.

    Called by the :mod:`apps.catalog.management.commands.seed_demo`
    management command and by :func:`apps.pos.bootstrap.ensure_bootstrapped`
    when the catalog is empty on the very first launch.
    """

    if Category.objects.exists():
        return

    with transaction.atomic():
        drinks = Category.objects.create(name="Напитки", slug="drinks", order=1, color="#f2b134")
        desserts = Category.objects.create(name="Десерты", slug="desserts", order=2, color="#ff8ba7")
        snacks = Category.objects.create(name="Закуски", slug="snacks", order=3, color="#7ec4cf")

        milk = ModifierGroup.objects.create(
            name="Молоко", slug="milk",
            selection_mode=ModifierGroup.SELECTION_SINGLE, is_required=False, order=1,
        )
        Modifier.objects.bulk_create(
            [
                Modifier(group=milk, name="Обычное", price_delta=Decimal("0"), order=1),
                Modifier(group=milk, name="Овсяное", price_delta=Decimal("40"), order=2),
                Modifier(group=milk, name="Кокосовое", price_delta=Decimal("40"), order=3),
                Modifier(group=milk, name="Безлактозное", price_delta=Decimal("40"), order=4),
            ]
        )

        syrup = ModifierGroup.objects.create(
            name="Сиропы", slug="syrups",
            selection_mode=ModifierGroup.SELECTION_MULTI, is_required=False, order=2,
        )
        Modifier.objects.bulk_create(
            [
                Modifier(group=syrup, name="Карамель", price_delta=Decimal("30"), order=1),
                Modifier(group=syrup, name="Ваниль", price_delta=Decimal("30"), order=2),
                Modifier(group=syrup, name="Лесной орех", price_delta=Decimal("30"), order=3),
            ]
        )

        products: Iterable[Product] = [
            Product.objects.create(name="Эспрессо", price=Decimal("120"), category=drinks, order=1),
            Product.objects.create(name="Американо", price=Decimal("150"), category=drinks, order=2),
            Product.objects.create(name="Капучино", price=Decimal("200"), category=drinks, order=3),
            Product.objects.create(name="Латте", price=Decimal("220"), category=drinks, order=4),
            Product.objects.create(name="Раф", price=Decimal("240"), category=drinks, order=5),
            Product.objects.create(name="Чай", price=Decimal("130"), category=drinks, order=6),
            Product.objects.create(name="Матча", price=Decimal("260"), category=drinks, order=7),
            Product.objects.create(name="Круассан", price=Decimal("140"), category=desserts, order=1),
            Product.objects.create(name="Шоколадный маффин", price=Decimal("160"), category=desserts, order=2),
            Product.objects.create(name="Сэндвич с курицей", price=Decimal("220"), category=snacks, order=1),
            Product.objects.create(name="Гранола", price=Decimal("180"), category=snacks, order=2),
        ]

        for product in products:
            if product.category_id == drinks.id:
                product.modifier_groups.set([milk, syrup])
