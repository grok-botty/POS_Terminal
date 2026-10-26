"""Тесты сервисного слоя приложения analytics."""

from decimal import Decimal

from django.test import TestCase

from apps.analytics import services as an
from apps.catalog.models import Category, Product
from apps.orders import services as os_
from apps.orders.models import Order


class CloseDayTests(TestCase):
    def setUp(self) -> None:
        cat = Category.objects.create(name="Напитки", slug="drinks", order=1)
        self.latte = Product.objects.create(
            name="Латте", price=Decimal("200"), category=cat
        )
        self.tea = Product.objects.create(
            name="Чай", price=Decimal("150"), category=cat
        )

    def _paid(self, product, qty=1):
        o = os_.create_order()
        os_.add_line(o, product, quantity=qty)
        os_.pay_order(o)
        return o

    def test_close_day_aggregates_paid_only(self) -> None:
        self._paid(self.latte, 2)      # 400
        self._paid(self.tea, 1)        # 150
        unpaid = os_.create_order()
        os_.add_line(unpaid, self.tea, quantity=5)  # 750 but not paid

        summary = an.close_day()

        self.assertEqual(summary.total_orders, 3)
        self.assertEqual(summary.paid_orders, 2)
        self.assertEqual(summary.unpaid_orders, 1)
        self.assertEqual(summary.total_revenue, Decimal("550.00"))
        self.assertEqual(summary.avg_check, Decimal("275.00"))

    def test_close_day_is_idempotent(self) -> None:
        self._paid(self.latte)
        first = an.close_day()
        second = an.close_day()
        self.assertEqual(first.pk, second.pk)

    def test_top_products_subtracts_own_cup_per_unit(self) -> None:
        own = self._paid(self.latte, 2)
        os_.update_line(own.lines.get(), fulfilment=Order.Fulfilment.OWN_CUP)
        self._paid(self.tea, 1)

        rows = {row["name_snapshot"]: row for row in an.top_products()}
        self.assertEqual(rows["Латте"]["qty"], 2)
        self.assertEqual(rows["Латте"]["revenue"], Decimal("360.00"))
        self.assertEqual(rows["Чай"]["revenue"], Decimal("150.00"))
