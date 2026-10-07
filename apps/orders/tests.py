"""Интеграционные тесты сервисного слоя приложения orders."""

from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

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

    def test_place_defaults_to_here(self) -> None:
        here = services.create_order()
        self.assertEqual(here.fulfilment, Order.Fulfilment.HERE)
        self.assertFalse(here.is_takeaway())
        self.assertEqual(here.place_mark(), "☕")
        self.assertEqual(here.place_title(), "здесь")

        away = services.create_order(fulfilment=Order.Fulfilment.TO_GO)
        self.assertTrue(away.is_takeaway())
        self.assertEqual(away.place_mark(), "🏃")
        self.assertEqual(away.place_title(), "на вынос")
        services.update_order_meta(away, fulfilment=Order.Fulfilment.HERE)
        away.refresh_from_db()
        self.assertFalse(away.is_takeaway())

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

    def test_open_shift_uses_the_given_date_and_refuses_a_second_one(self) -> None:
        before = timezone.now()
        shift = services.open_shift(business_date=date(2020, 1, 2), start_time=time(18, 15))
        after = timezone.now()
        self.assertEqual(shift.business_date, date(2020, 1, 2))
        self.assertEqual(shift.start_time, time(18, 15))
        self.assertIsNotNone(shift.opened_at)
        self.assertGreaterEqual(shift.opened_at, before)
        self.assertLessEqual(shift.opened_at, after)
        self.assertTrue(shift.is_open)
        with self.assertRaises(services.ShiftError):
            services.open_shift(business_date=date(2020, 1, 3), start_time=time(19, 30))
        with self.assertRaises(services.ShiftError):
            services.open_shift(business_date=None)

    def test_close_shift_requires_phrase_and_leaves_unfinished_orders(self) -> None:
        shift = services.open_shift(business_date=date(2026, 10, 5))
        order = services.create_order()
        services.add_line(order, self.latte, quantity=1)
        services.enqueue_order(order)
        with self.assertRaises(services.ShiftError):
            services.close_shift(shift, confirmation="закрыть")
        shift.refresh_from_db()
        self.assertTrue(shift.is_open)
        services.close_shift(shift, confirmation=" ЗАКРЫТЬ ")
        shift.refresh_from_db()
        order.refresh_from_db()
        self.assertFalse(shift.is_open)
        self.assertIsNone(shift.closed_at)
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)

    def test_stats_group_by_shift_business_date(self) -> None:
        early = Shift.objects.create(business_date=date(2026, 10, 1), is_open=False)
        late = services.open_shift(business_date=date(2026, 10, 5))
        morning = services.create_order()
        services.add_line(morning, self.latte, quantity=2)
        morning.shift = early
        services.pay_order(morning)
        services.mark_ready(morning)
        evening = services.create_order()
        services.add_line(evening, self.latte, quantity=1)
        evening.shift = late
        services.pay_order(evening)
        services.mark_ready(evening)

        current = services.aggregate_shift_stats(services.select_shifts(period="this"))
        self.assertEqual([s.id for s in current["shifts"]], [late.id])
        self.assertEqual(current["revenue"], Decimal("200.00"))
        self.assertEqual(current["issued"], 1)

        ranged = services.aggregate_shift_stats(
            services.select_shifts(date_from=date(2026, 10, 1), date_to=date(2026, 10, 1))
        )
        self.assertEqual([s.id for s in ranged["shifts"]], [early.id])
        self.assertEqual(ranged["revenue"], Decimal("400.00"))
        self.assertEqual(ranged["issued"], 1)
        self.assertEqual(
            [(row["date"], row["revenue"]) for row in ranged["by_date"]],
            [(date(2026, 10, 1), Decimal("400.00"))],
        )
        both = services.aggregate_shift_stats([early, late])
        self.assertEqual(
            [(row["date"], row["revenue"]) for row in both["by_date"]],
            [
                (date(2026, 10, 1), Decimal("400.00")),
                (date(2026, 10, 5), Decimal("200.00")),
            ],
        )

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

    def test_shift_clock_uses_elapsed_time_not_the_absolute_clock(self) -> None:
        opened = datetime(2010, 6, 1, 4, 5, tzinfo=dt_timezone.utc)
        shift = Shift.objects.create(
            business_date=date(2026, 10, 5),
            start_time=time(19, 30),
            opened_at=opened,
            is_open=True,
        )
        order = services.create_order()
        services.add_line(order, self.latte, quantity=1)
        order.shift = shift
        services.pay_order(order)
        order.paid_at = opened + timedelta(hours=4, minutes=45)
        order.save(update_fields=["paid_at"])
        services.mark_ready(order)
        order.ready_at = opened + timedelta(hours=5)
        order.save(update_fields=["ready_at"])

        order.refresh_from_db()
        self.assertEqual(order.payment_clock(), "00:15")
        self.assertEqual(order.handout_clock(), "00:30")
        self.assertNotEqual(order.paid_at.hour, 0)

        load = services.load_over_time([shift])
        self.assertEqual(load["bucket_minutes"], 30)
        labels = [(row["label"], row["count"]) for row in load["points"]]
        self.assertEqual(labels[0], ("19:30", 0))
        self.assertEqual(labels[-1], ("00:00", 1))
        self.assertNotIn("04:05", [row["label"] for row in load["points"]])
        self.assertNotIn("08:50", [row["label"] for row in load["points"]])

    def test_load_buckets_follow_the_selected_shifts_and_widen(self) -> None:
        opened = datetime(2011, 1, 1, 2, 0, tzinfo=dt_timezone.utc)
        early = Shift.objects.create(
            business_date=date(2026, 10, 1),
            start_time=time(19, 30),
            opened_at=opened,
            is_open=False,
        )
        late = Shift.objects.create(
            business_date=date(2026, 10, 5),
            start_time=time(19, 30),
            opened_at=opened,
            is_open=True,
        )
        first = services.create_order()
        services.add_line(first, self.latte, quantity=1)
        first.shift = early
        services.pay_order(first)
        first.paid_at = opened + timedelta(minutes=20)
        first.save(update_fields=["paid_at"])

        second = services.create_order()
        services.add_line(second, self.latte, quantity=1)
        second.shift = late
        services.pay_order(second)
        second.paid_at = opened + timedelta(hours=9)
        second.save(update_fields=["paid_at"])

        current = services.load_over_time(services.select_shifts(period="this"))
        self.assertEqual(
            [(row["label"], row["count"]) for row in current["points"]],
            [("19:30", 0), ("20:30", 0), ("21:30", 0), ("22:30", 0), ("23:30", 0), ("00:30", 0), ("01:30", 0), ("02:30", 0), ("03:30", 0), ("04:30", 1)],
        )
        self.assertEqual(current["bucket_minutes"], 60)
        only_early = services.load_over_time(
            services.select_shifts(date_from=date(2026, 10, 1), date_to=date(2026, 10, 1))
        )
        self.assertEqual(
            [(row["label"], row["count"]) for row in only_early["points"]],
            [("19:30", 1)],
        )
        self.assertEqual(only_early["bucket_minutes"], 30)


class HandoutAndQueuesTests(TestCase):
    """Галочки «отдали», автоперевод в «Готово» и три очереди смены."""

    def setUp(self) -> None:
        self.cat = Category.objects.create(name="Напитки", slug="drinks")
        self.latte = Product.objects.create(
            name="Латте", price=Decimal("200"), category=self.cat
        )
        self.t0 = datetime(2026, 10, 7, 16, 0, tzinfo=dt_timezone.utc)
        with patch("apps.orders.services.timezone.now", return_value=self.t0):
            self.shift = services.open_shift(
                business_date=date(2026, 10, 7), start_time=time(19, 0)
            )

    def _paid(self, name: str) -> Order:
        order = services.create_order(guest_name=name)
        services.add_line(order, self.latte, quantity=1)
        services.pay_order(order)
        order.refresh_from_db()
        return order

    def test_all_handed_and_paid_arms_then_uncheck_or_unpay_cancels(self) -> None:
        order = self._paid("Маша")
        line = order.lines.get()
        self.assertIsNone(order.auto_ready_at)

        services.set_line_handed_out(line, True)
        order.refresh_from_db()
        self.assertIsNotNone(order.auto_ready_at)
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)

        unpaid = services.create_order(guest_name="Без денег")
        services.add_line(unpaid, self.latte, quantity=1)
        services.enqueue_order(unpaid)
        services.set_line_handed_out(unpaid.lines.get(), True)
        unpaid.refresh_from_db()
        self.assertIsNone(unpaid.auto_ready_at)

        services.set_line_handed_out(line, False)
        order.refresh_from_db()
        self.assertIsNone(order.auto_ready_at)

        with patch("apps.orders.services.timezone.now", return_value=self.t0):
            services.set_line_handed_out(line, True)
        order.refresh_from_db()
        self.assertEqual(order.auto_ready_at, self.t0)
        services.unpay_order(order)
        order.refresh_from_db()
        self.assertFalse(order.is_paid)
        self.assertIsNone(order.auto_ready_at)
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)

        with patch(
            "apps.orders.services.timezone.now",
            return_value=self.t0 + timedelta(seconds=10),
        ):
            services.settle_due_auto_ready(self.shift)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)

    def test_auto_ready_after_five_seconds_sets_handout_time(self) -> None:
        with patch("apps.orders.services.timezone.now", return_value=self.t0):
            order = self._paid("Лена")
            services.set_line_handed_out(order.lines.get(), True)
        order.refresh_from_db()
        self.assertEqual(order.auto_ready_at, self.t0)

        with patch(
            "apps.orders.services.timezone.now",
            return_value=self.t0 + timedelta(seconds=4),
        ):
            self.assertEqual(services.settle_due_auto_ready(self.shift), 0)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)
        self.assertEqual(order.handout_clock(), "")

        due = self.t0 + timedelta(seconds=5)
        with patch("apps.orders.services.timezone.now", return_value=due):
            self.assertEqual(services.settle_due_auto_ready(self.shift), 1)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.READY)
        self.assertEqual(order.ready_at, due)
        self.assertEqual(order.handout_clock(), "19:00")
        self.assertEqual(order.main_queue_until, due + timedelta(seconds=13))

    def test_new_line_cancels_the_countdown(self) -> None:
        with patch("apps.orders.services.timezone.now", return_value=self.t0):
            order = self._paid("Кира")
            services.set_line_handed_out(order.lines.get(), True)
        services.add_line(order, self.latte, quantity=1)
        order.refresh_from_db()
        self.assertIsNone(order.auto_ready_at)
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)

    def test_paid_ready_and_cancelled_leave_the_main_queue_after_hold(self) -> None:
        with patch("apps.orders.services.timezone.now", return_value=self.t0):
            ready = self._paid("Готовый")
            cancelled = self._paid("Отменённый")
            still = self._paid("В работе")
            services.mark_ready(ready)
            services.cancel_order(cancelled)
        Order.objects.filter(pk=ready.pk).update(created_at=self.t0)
        Order.objects.filter(pk=cancelled.pk).update(
            created_at=self.t0 + timedelta(minutes=1)
        )
        Order.objects.filter(pk=still.pk).update(
            created_at=self.t0 + timedelta(minutes=2)
        )

        holding = self.t0 + timedelta(seconds=12)
        with patch("apps.orders.services.timezone.now", return_value=holding):
            active = [order.id for order in services.barista_queue("active")]
            self.assertEqual(active, [ready.id, cancelled.id, still.id])
            self.assertEqual(services.barista_queue("ready"), [])
            self.assertEqual(services.barista_queue("cancelled"), [])

        left = self.t0 + timedelta(seconds=13)
        with patch("apps.orders.services.timezone.now", return_value=left):
            active = [order.id for order in services.barista_queue("active")]
            ready_ids = [order.id for order in services.barista_queue("ready")]
            cancelled_ids = [order.id for order in services.barista_queue("cancelled")]
        self.assertEqual(active, [still.id])
        self.assertEqual(ready_ids, [ready.id])
        self.assertEqual(cancelled_ids, [cancelled.id])

        with patch("apps.orders.services.timezone.now", return_value=self.t0):
            services.set_barista_status(ready, Order.Status.READY)
        ready.refresh_from_db()
        self.assertEqual(ready.ready_at, self.t0)
        self.assertEqual(ready.main_queue_until, self.t0 + timedelta(seconds=13))

    def test_unpaid_ready_stays_until_payment_starts_the_hold(self) -> None:
        order = services.create_order(guest_name="Должен")
        services.add_line(order, self.latte, quantity=1)
        services.enqueue_order(order)
        services.mark_ready(order)
        order.refresh_from_db()
        self.assertFalse(order.is_paid)
        self.assertIsNone(order.main_queue_until)
        self.assertEqual(
            [item.id for item in services.barista_queue("active")], [order.id]
        )
        self.assertEqual(services.barista_queue("ready"), [])

        with patch("apps.orders.services.timezone.now", return_value=self.t0):
            services.pay_order(order)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.READY)
        self.assertEqual(order.main_queue_until, self.t0 + timedelta(seconds=13))
        self.assertEqual(
            [item.id for item in services.barista_queue("active")], [order.id]
        )

    def test_other_shifts_are_hidden(self) -> None:
        foreign_shift = Shift.objects.create(
            business_date=date(2026, 1, 1), is_open=False
        )
        foreign = self._paid("Чужая смена")
        foreign.shift = foreign_shift
        foreign.save(update_fields=["shift"])
        self.assertEqual(services.barista_queue("active"), [])
