"""Интеграционные тесты сервисного слоя приложения orders."""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.catalog.models import Category, Modifier, ModifierGroup, Product
from apps.orders import services
from apps.orders.models import Order, Shift


class OrderServicesTests(TestCase):
    def setUp(self) -> None:
        self.cat = Category.objects.create(name="Напитки", slug="drinks", order=1)
        self.milk = ModifierGroup.objects.create(
            name="Молоко", slug="milk",
            selection_mode=ModifierGroup.SELECTION_SINGLE,
        )
        self.milk_oat = Modifier.objects.create(
            group=self.milk, name="Овсяное", price_delta=Decimal("40")
        )
        self.milk_reg = Modifier.objects.create(
            group=self.milk, name="Обычное", price_delta=Decimal("0")
        )
        self.syrup = ModifierGroup.objects.create(
            name="Сиропы", slug="syrups",
            selection_mode=ModifierGroup.SELECTION_MULTI,
        )
        self.syrup_car = Modifier.objects.create(
            group=self.syrup, name="Карамель", price_delta=Decimal("30")
        )
        self.syrup_van = Modifier.objects.create(
            group=self.syrup, name="Ваниль", price_delta=Decimal("30")
        )
        self.latte = Product.objects.create(
            name="Латте", price=Decimal("200"), category=self.cat
        )
        self.latte.modifier_groups.add(self.milk, self.syrup)

    def test_add_line_computes_total_with_modifiers(self) -> None:
        order = services.create_order()
        services.add_line(
            order,
            self.latte,
            quantity=2,
            modifier_ids=[self.milk_oat.id, self.syrup_car.id, self.syrup_van.id],
        )
        # (200 base + 40 oat + 30 caramel + 30 vanilla) * 2 = 600
        self.assertEqual(order.total_amount, Decimal("600.00"))

    def test_single_choice_modifier_group_rejects_two_options(self) -> None:
        order = services.create_order()
        with self.assertRaises(ValueError):
            services.add_line(
                order,
                self.latte,
                modifier_ids=[self.milk_oat.id, self.milk_reg.id],
            )

    def test_pay_requires_at_least_one_line(self) -> None:
        order = services.create_order()
        with self.assertRaises(ValueError):
            services.pay_order(order)

    def test_full_lifecycle(self) -> None:
        order = services.create_order()
        services.add_line(order, self.latte, quantity=1)
        services.pay_order(order)
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)

        services.mark_ready(order)
        self.assertEqual(order.status, Order.Status.READY)

        services.hand_off(order)
        self.assertEqual(order.status, Order.Status.HANDED_OFF)

    def test_addon_prices_add_to_line_total(self) -> None:
        """База + молоко + размер + сироп, затем удвоение количества."""
        order = services.create_order()
        services.add_line(
            order,
            self.latte,
            quantity=1,
            modifier_ids=[self.milk_oat.id, self.syrup_van.id],
        )
        # 200 + 40 овсяное + 30 ваниль
        self.assertEqual(order.total_amount, Decimal("270.00"))
        line = order.lines.get()
        self.assertEqual(line.subtotal(), Decimal("270.00"))

        services.change_line_quantity(line, 2)
        order.refresh_from_db()
        self.assertEqual(order.total_amount, Decimal("540.00"))

    def test_update_line_recalculates_when_addons_change(self) -> None:
        order = services.create_order()
        line = services.add_line(order, self.latte, modifier_ids=[self.milk_reg.id])
        self.assertEqual(order.total_amount, Decimal("200.00"))
        services.update_line(line, modifier_ids=[self.milk_oat.id, self.syrup_car.id])
        order.refresh_from_db()
        # 200 + 40 + 30
        self.assertEqual(order.total_amount, Decimal("270.00"))

    def test_cycle_barista_status(self) -> None:
        order = services.create_order()
        services.add_line(order, self.latte, quantity=1)
        services.pay_order(order)
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)
        self.assertEqual(order.barista_label(), "Не готово")

        services.cycle_barista_status(order)
        self.assertEqual(order.status, Order.Status.READY)
        self.assertEqual(order.barista_label(), "Готово")

        services.cycle_barista_status(order)
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(order.barista_label(), "Отменено")

        services.cycle_barista_status(order)
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)
        self.assertIsNone(order.ready_at)

    def test_pay_attaches_open_shift_not_the_wall_clock(self) -> None:
        shift = Shift.objects.create(business_date=date(2026, 10, 5), is_open=True)
        order = services.create_order()
        services.add_line(order, self.latte, quantity=1)
        services.pay_order(order)
        order.refresh_from_db()
        self.assertEqual(order.shift_id, shift.id)
        self.assertEqual(services.current_business_date(), date(2026, 10, 5))

    def test_business_date_is_empty_without_a_shift(self) -> None:
        self.assertIsNone(services.current_business_date())

    def test_all_ready_bulk_action(self) -> None:
        for _ in range(3):
            o = services.create_order()
            services.add_line(o, self.latte, quantity=1)
            services.pay_order(o)
        n = services.mark_all_ready()
        self.assertEqual(n, 3)
        self.assertEqual(
            Order.objects.filter(status=Order.Status.READY).count(), 3
        )
