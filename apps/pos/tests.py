"""Тесты экрана кассы: допы, очередь и цикл статуса."""

from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Category, Modifier, ModifierGroup, Product
from apps.orders import services
from apps.orders.models import Order, Shift
from apps.pos.views import FUNNY_GUESTS, SESSION_ORDER_KEY


User = get_user_model()


class RegisterScreenTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="cashier", password="cashier")
        cls.cat = Category.objects.create(name="Классика", slug="klassika", order=1)
        cls.food = Category.objects.create(name="Еда", slug="eda", order=2)
        cls.milk = ModifierGroup.objects.create(
            name="Молоко", slug="milk", selection_mode=ModifierGroup.SELECTION_SINGLE
        )
        cls.oat = Modifier.objects.create(
            group=cls.milk, name="овсяное", price_delta=Decimal("30"), order=2
        )
        cls.regular = Modifier.objects.create(
            group=cls.milk, name="обычное", price_delta=Decimal("0"),
            is_default=True, order=1,
        )
        cls.latte = Product.objects.create(
            name="Латте", price=Decimal("220"), category=cls.cat
        )
        cls.latte.modifier_groups.add(cls.milk)
        cls.espresso = Product.objects.create(
            name="Эспрессо", price=Decimal("150"), category=cls.cat, order=2
        )
        cls.croissant = Product.objects.create(
            name="Круассан", price=Decimal("120"), category=cls.food
        )
        cls.shift = Shift.objects.create(
            business_date=date(2026, 10, 5), is_open=True, opened_by=cls.user
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_register_shows_shared_bar_and_sections(self):
        response = self.client.get(reverse("pos:register"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Очередь")
        self.assertContains(response, "клик меняет статус")
        self.assertContains(response, ">Все<")
        self.assertContains(response, 'id="menu-search"')
        self.assertContains(response, "—— Классика ——")
        self.assertContains(response, "—— Еда ——")
        self.assertContains(response, "допы →")
        self.assertContains(response, "Оплачено")
        self.assertNotContains(response, "Оплатить")
        self.assertContains(response, 'href="/catalog/"')
        order = Order.objects.get(status=Order.Status.NEW)
        self.assertIn(order.guest_name, FUNNY_GUESTS)
        self.assertContains(response, order.guest_name)

    def test_menu_search_filters_tiles_by_name_inside_the_tag(self):
        url = reverse("pos:products_grid")
        narrowed = self.client.get(url, {"q": "лат"})
        self.assertContains(narrowed, "Латте")
        self.assertNotContains(narrowed, "Эспрессо")
        self.assertNotContains(narrowed, "Круассан")
        self.assertContains(narrowed, reverse("pos:modifier_picker", args=[self.latte.id]))

        upper = self.client.get(url, {"q": "ЭСПР"})
        self.assertContains(upper, "Эспрессо")
        self.assertContains(upper, reverse("pos:add_line", args=[self.espresso.id]))
        self.assertNotContains(upper, "Латте")

        tagged = self.client.get(url, {"q": "лат", "category": self.food.id})
        self.assertNotContains(tagged, "Латте")
        self.assertContains(tagged, "Ничего не найдено")

        in_tag = self.client.get(url, {"q": "кру", "category": self.food.id})
        self.assertContains(in_tag, "Круассан")
        self.assertNotContains(in_tag, "Эспрессо")

        cleared = self.client.get(
            url, {"q": "   ", "category": self.cat.id}
        )
        self.assertContains(cleared, "Латте")
        self.assertContains(cleared, "Эспрессо")
        self.assertNotContains(cleared, "Круассан")

        body = self.client.get(
            url, {"q": "лат"}, HTTP_HX_TARGET="menu-body"
        )
        self.assertContains(body, "Латте")
        self.assertNotContains(body, 'id="menu-search"')
        self.assertNotContains(body, "menu-tab")

    def test_item_without_addons_is_one_tap(self):
        self.client.get(reverse("pos:register"))
        response = self.client.post(reverse("pos:add_line", args=[self.espresso.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Эспрессо")
        self.assertContains(response, "150 ₽")
        order = Order.objects.get(status=Order.Status.NEW)
        self.assertEqual(order.total_amount, Decimal("150.00"))

    def test_addon_sheet_preselects_default_and_prices_the_line(self):
        response = self.client.get(reverse("pos:modifier_picker", args=[self.latte.id]))
        self.assertContains(response, "Латте · допы")
        self.assertContains(response, "обычное")
        self.assertContains(response, "checked")
        self.assertContains(response, "+30₽")

        self.client.get(reverse("pos:register"))
        response = self.client.post(
            reverse("pos:add_line", args=[self.latte.id]),
            data={"group_%s" % self.milk.id: str(self.oat.id)},
        )
        self.assertContains(response, "+ овсяное +30₽")
        self.assertContains(response, "250 ₽")
        order = Order.objects.get(status=Order.Status.NEW)
        self.assertEqual(order.total_amount, Decimal("250.00"))

    def test_status_cycle_returns_fragment_without_reload(self):
        order = services.create_order(guest_name="Маша")
        services.add_line(order, self.espresso, quantity=1)
        services.pay_order(order)

        response = self.client.post(reverse("pos:queue_cycle", args=[order.id]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<html")
        self.assertContains(response, "Готово")
        self.assertContains(response, "Маша")
        self.assertNotContains(response, "150 ₽")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.READY)

        response = self.client.post(reverse("pos:queue_cycle", args=[order.id]))
        self.assertContains(response, "Отменено")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

        self.client.post(reverse("pos:queue_cycle", args=[order.id]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)

    def test_context_menu_sets_readiness_without_touching_payment(self):
        order = services.create_order(guest_name="Маша")
        services.add_line(order, self.espresso, quantity=1)
        services.enqueue_order(order)

        response = self.client.post(
            reverse("pos:queue_status", args=[order.id]),
            data={"status": "cancelled"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Отменено")
        self.assertContains(response, "💸")
        self.assertContains(response, "data-status-url")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertFalse(order.is_paid)
        self.assertIsNone(order.ready_at)

        ready = self.client.post(
            reverse("pos:queue_status", args=[order.id]),
            data={"status": "ready"},
        )
        self.assertContains(ready, "Готово")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.READY)
        self.assertIsNotNone(order.ready_at)
        self.assertFalse(order.is_paid)

        back = self.client.post(
            reverse("pos:queue_status", args=[order.id]),
            data={"status": "in_progress"},
        )
        self.assertContains(back, "Не готово")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)
        self.assertIsNone(order.ready_at)

        refused = self.client.post(
            reverse("pos:queue_status", args=[order.id]),
            data={"status": "handed_off"},
        )
        self.assertEqual(refused.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)
        self.assertFalse(order.is_paid)

    def test_meta_and_pay_keep_the_guest_name(self):
        self.client.get(reverse("pos:register"))
        response = self.client.post(
            reverse("pos:order_meta"),
            data={"guest_name": "Маша", "comment": "без сахара"},
        )
        self.assertEqual(response.status_code, 204)
        draft = Order.objects.get(status=Order.Status.NEW)
        self.assertEqual(draft.guest_name, "Маша")
        self.assertEqual(draft.comment, "без сахара")

        self.client.post(reverse("pos:add_line", args=[self.espresso.id]))
        self.client.post(
            reverse("pos:order_pay"),
            data={"guest_name": "Маша", "comment": "крышка отдельно"},
        )
        paid = Order.objects.get(is_paid=True)
        self.assertEqual(paid.guest_name, "Маша")
        self.assertEqual(paid.comment, "крышка отдельно")
        self.assertEqual(paid.barista_label(), "Не готово")

    def test_enqueue_sends_unpaid_order_to_the_queue(self):
        self.client.get(reverse("pos:register"))
        self.client.post(reverse("pos:add_line", args=[self.espresso.id]))
        response = self.client.post(
            reverse("pos:order_enqueue"),
            data={"guest_name": "Квакша", "comment": "оба больших"},
        )
        self.assertEqual(response.status_code, 204)
        order = Order.objects.get(guest_name="Квакша")
        self.assertFalse(order.is_paid)
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)
        self.assertEqual(order.comment, "оба больших")

    def test_queue_shows_unpaid_until_the_order_is_paid(self):
        self.client.get(reverse("pos:register"))
        self.client.post(reverse("pos:add_line", args=[self.espresso.id]))
        self.client.post(
            reverse("pos:order_enqueue"),
            data={"guest_name": "Квакша"},
        )
        unpaid = Order.objects.get(guest_name="Квакша")
        self.assertEqual(unpaid.unpaid_label(), "не оплачено")
        queue = self.client.get(reverse("pos:queue_fragment"))
        self.assertContains(queue, "💸")
        self.assertContains(queue, 'title="не оплачено"')
        self.assertContains(queue, 'aria-label="не оплачено"')
        self.assertContains(queue, 'class="q-lines"')
        self.assertNotContains(queue, ">не оплачено<")
        self.assertContains(queue, "Не готово")
        self.assertContains(queue, "event.stopPropagation()")

        services.cycle_barista_status(unpaid)
        unpaid.refresh_from_db()
        self.assertEqual(unpaid.status, Order.Status.READY)
        self.assertFalse(unpaid.is_paid)

        services.pay_order(unpaid)
        unpaid.refresh_from_db()
        self.assertTrue(unpaid.is_paid)
        self.assertEqual(unpaid.status, Order.Status.READY)
        self.assertEqual(unpaid.barista_label(), "Готово")
        self.assertEqual(unpaid.unpaid_label(), "")
        queue = self.client.get(reverse("pos:queue_fragment"))
        self.assertNotContains(queue, "💸")
        self.assertNotContains(queue, "не оплачено")
        self.assertContains(queue, "Готово")

    def test_open_queue_card_loads_and_edits_the_right_panel(self):
        order = services.create_order(
            guest_name="Маша", fulfilment=Order.Fulfilment.TO_GO
        )
        services.update_order_meta(order, comment="без сахара")
        services.add_line(
            order, self.latte, quantity=2, modifier_ids=[self.oat.id]
        )
        services.enqueue_order(order)

        self.client.get(reverse("pos:register"))
        self.client.post(reverse("pos:add_line", args=[self.croissant.id]))
        draft = Order.objects.get(status=Order.Status.NEW)

        response = self.client.get(reverse("pos:queue_open", args=[order.id]))
        self.assertContains(response, "Маша")
        self.assertContains(response, "без сахара")
        self.assertContains(response, "Латте")
        self.assertContains(response, "+ овсяное +30₽")
        self.assertContains(response, "Из очереди")
        self.assertContains(response, "не оплачено")
        self.assertContains(response, "Новый чек")
        self.assertContains(response, 'value="to_go" checked')
        self.assertContains(response, ">на вынос<")
        self.assertContains(response, ">здесь<")
        self.assertContains(response, ">2<")
        self.assertNotContains(response, "В очередь")

        draft.refresh_from_db()
        self.assertEqual(draft.status, Order.Status.IN_PROGRESS)
        self.assertFalse(draft.is_paid)

        line = order.lines.get()
        edited = self.client.post(reverse("pos:line_inc", args=[line.id]))
        self.assertContains(edited, ">3<")
        line.refresh_from_db()
        self.assertEqual(line.quantity, 3)

        sheet = self.client.get(reverse("pos:line_edit", args=[line.id]))
        self.assertContains(sheet, "Латте · допы")

        self.client.post(
            reverse("pos:order_pay"),
            data={"guest_name": "Маша", "comment": "без сахара"},
        )
        order.refresh_from_db()
        self.assertTrue(order.is_paid)
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)
        queue = self.client.get(reverse("pos:queue_fragment"))
        self.assertEqual(queue.content.decode().count("💸"), 1)
        self.assertEqual(queue.content.decode().count("не оплачено"), 2)

        self.client.get(reverse("pos:queue_open", args=[order.id]))
        released = self.client.post(reverse("pos:order_discard"))
        self.assertEqual(released.status_code, 204)
        self.assertTrue(Order.objects.filter(pk=order.id).exists())

    def test_empty_draft_is_dropped_when_a_queue_card_opens(self):
        self.client.get(reverse("pos:register"))
        empty = Order.objects.get(status=Order.Status.NEW)
        order = services.create_order(guest_name="Аня")
        services.add_line(order, self.espresso, quantity=1)
        services.enqueue_order(order)
        self.client.get(reverse("pos:queue_open", args=[order.id]))
        self.assertFalse(Order.objects.filter(pk=empty.id).exists())
        panel = self.client.get(reverse("pos:order_panel"))
        self.assertContains(panel, "Аня")

    def test_editing_a_line_reopens_the_sheet(self):
        self.client.get(reverse("pos:register"))
        self.client.post(
            reverse("pos:add_line", args=[self.latte.id]),
            data={"group_%s" % self.milk.id: str(self.regular.id)},
        )
        line = Order.objects.get(status=Order.Status.NEW).lines.get()
        response = self.client.get(reverse("pos:line_edit", args=[line.id]))
        self.assertContains(response, "Латте · допы")
        self.assertContains(response, "В заказ")

    def test_place_toggle_defaults_to_here_and_edits_a_reopened_order(self):
        panel = self.client.get(reverse("pos:register"))
        self.assertContains(panel, 'name="fulfilment" value="here" checked')
        self.assertContains(panel, ">здесь<")
        self.assertContains(panel, ">на вынос<")
        self.assertNotContains(panel, 'name="fulfilment" value="here" disabled')
        self.assertNotContains(panel, 'name="fulfilment" value="to_go" disabled')
        draft = Order.objects.get(status=Order.Status.NEW)
        self.assertEqual(draft.fulfilment, Order.Fulfilment.HERE)
        self.assertFalse(draft.is_takeaway())

        switched = self.client.post(
            reverse("pos:order_meta"), {"fulfilment": Order.Fulfilment.TO_GO}
        )
        self.assertEqual(switched.status_code, 204)
        draft.refresh_from_db()
        self.assertTrue(draft.is_takeaway())

        services.add_line(draft, self.espresso, quantity=1)
        services.enqueue_order(draft)
        opened = self.client.get(reverse("pos:queue_open", args=[draft.id]))
        self.assertContains(opened, 'value="to_go" checked')
        self.assertNotContains(opened, 'name="fulfilment" value="to_go" disabled')

        edited = self.client.post(
            reverse("pos:order_meta"), {"fulfilment": Order.Fulfilment.HERE}
        )
        self.assertEqual(edited.status_code, 204)
        draft.refresh_from_db()
        self.assertFalse(draft.is_takeaway())
        queue = self.client.get(reverse("pos:queue_fragment"))
        self.assertContains(queue, "place-pill-here")
        self.assertContains(queue, 'title="здесь"')
        self.assertContains(queue, "☕")
        self.assertNotContains(queue, "place-pill-to_go")


class ShiftScreenTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cashier", password="pw")
        self.client.force_login(self.user)
        self.cat = Category.objects.create(name="Классика", slug="klassika")
        self.latte = Product.objects.create(
            name="Латте", price=Decimal("200"), category=self.cat
        )

    def test_tabs_stay_locked_until_a_shift_is_open(self):
        response = self.client.get(reverse("pos:shift"))
        self.assertContains(response, "Открыть смену")
        self.assertContains(response, "Смена не открыта")
        self.assertContains(response, "is-disabled")
        self.assertContains(response, 'href="/catalog/"')
        self.assertRedirects(
            self.client.get(reverse("pos:register")), reverse("pos:shift")
        )
        stats = self.client.get(reverse("pos:stats"))
        self.assertEqual(stats.status_code, 200)
        self.assertContains(stats, "Статистика")
        body = response.content.decode()
        stats_link = body[body.index('href="/pos/stats/"'):body.index("</a>", body.index('href="/pos/stats/"'))]
        menu_link = body[body.index('href="/catalog/"'):body.index("</a>", body.index('href="/catalog/"'))]
        self.assertNotIn("aria-disabled", stats_link)
        self.assertNotIn("aria-disabled", menu_link)
        self.assertIn("aria-disabled", body[body.index('href="/pos/"'):body.index("</a>", body.index(">Касса<"))])

    def test_stats_works_with_no_shift_open(self):
        closed = Shift.objects.create(
            business_date=date(2026, 9, 1),
            is_open=False,
            start_time=time(19, 30),
            opened_at=datetime(2026, 9, 1, 16, 0, tzinfo=dt_timezone.utc),
        )
        order = services.create_order(guest_name="Архив")
        services.add_line(order, self.latte, quantity=1)
        order.shift = closed
        order.save(update_fields=["shift"])
        services.pay_order(order)
        services.mark_ready(order)
        self.assertFalse(Shift.objects.filter(is_open=True).exists())

        page = self.client.get(reverse("pos:stats") + "?period=all")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Статистика")
        self.assertContains(page, "Латте")
        self.assertEqual(page.context["stats"]["issued"], 1)
        self.assertEqual(page.context["stats"]["revenue"], Decimal("200.00"))

        current = self.client.get(reverse("pos:stats"))
        self.assertEqual(current.status_code, 200)
        self.assertContains(current, "За эту выборку смен нет.")
        self.assertEqual(current.context["stats"]["issued"], 0)

        exported = self.client.get(reverse("pos:stats_csv") + "?period=all")
        self.assertEqual(exported.status_code, 200)
        self.assertIn("Латте", exported.content.decode("utf-8-sig"))
        self.assertRedirects(
            self.client.get(reverse("pos:register")), reverse("pos:shift")
        )

    def test_open_shift_keeps_the_posted_date(self):
        form = self.client.get(reverse("pos:shift"))
        self.assertContains(form, 'name="start_time"')
        self.assertContains(form, 'value="19:30"')
        self.assertContains(form, "shift-when")
        response = self.client.post(
            reverse("pos:shift"),
            {
                "action": "open",
                "business_date": "2020-01-02",
                "start_time": "21:05",
            },
        )
        self.assertRedirects(response, reverse("pos:register"))
        shift = Shift.objects.get()
        self.assertEqual(shift.business_date, date(2020, 1, 2))
        self.assertEqual(shift.start_time, time(21, 5))
        self.assertTrue(shift.is_open)
        self.assertIsNotNone(shift.opened_at)
        self.assertEqual(shift.opened_by, self.user)
        self.assertEqual(shift.cashier_name, "cashier")
        self.assertNotEqual(shift.business_date, date(2026, 10, 6))

        Shift.objects.all().delete()
        response = self.client.post(reverse("pos:shift"), {"action": "open"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Укажите дату смены")
        self.assertFalse(Shift.objects.exists())

        missing_time = self.client.post(
            reverse("pos:shift"),
            {"action": "open", "business_date": "2020-01-02", "start_time": ""},
        )
        self.assertEqual(missing_time.status_code, 200)
        self.assertContains(missing_time, "Укажите время начала смены")
        self.assertFalse(Shift.objects.exists())

    def test_open_shift_stores_the_typed_cashier_name(self):
        page = self.client.get(reverse("pos:shift"))
        self.assertContains(page, "автор проги")
        self.assertContains(page, "https://t.me/LotFullKa")
        self.assertContains(page, 'target="_blank"')
        self.assertContains(page, 'rel="noopener"')
        self.assertContains(page, "@LotFullKa")
        self.assertContains(page, 'name="cashier_name"')
        self.assertContains(page, 'value="cashier"')
        response = self.client.post(
            reverse("pos:shift"),
            {
                "action": "open",
                "business_date": "2026-10-05",
                "start_time": "19:30",
                "cashier_name": "Маша на смене",
            },
        )
        self.assertRedirects(response, reverse("pos:register"))
        shift = Shift.objects.get()
        self.assertEqual(shift.cashier_name, "Маша на смене")
        till = self.client.get(reverse("pos:register"))
        self.assertContains(till, "Маша на смене")
        self.assertContains(till, "клик меняет статус")

    def test_anonymous_request_signs_in_as_admin(self):
        from django.test import Client

        guest = Client()
        response = guest.get(reverse("pos:shift"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Открыть смену")
        self.assertNotContains(response, "Вход в кассу")
        admin = User.objects.get(username="admin")
        self.assertTrue(admin.is_manager())
        self.assertRedirects(guest.get(reverse("pos:register")), reverse("pos:shift"))
        stats = guest.get(reverse("pos:stats"))
        self.assertEqual(stats.status_code, 200)
        self.assertContains(stats, "Статистика")

    def test_close_requires_the_exact_word_and_keeps_unfinished_orders(self):
        shift = Shift.objects.create(
            business_date=date(2026, 10, 5), is_open=True, opened_by=self.user
        )
        order = services.create_order(created_by=self.user)
        services.add_line(order, self.latte, quantity=1)
        services.enqueue_order(order)

        page = self.client.get(reverse("pos:shift"))
        self.assertContains(page, "Закрыть смену")
        self.assertContains(page, "Есть незавершённые заказы")
        self.assertContains(page, "5 октября 2026")

        refused = self.client.post(
            reverse("pos:shift"),
            {"action": "close", "confirmation": "закрыть"},
        )
        self.assertEqual(refused.status_code, 200)
        self.assertContains(refused, "ЗАКРЫТЬ")
        shift.refresh_from_db()
        self.assertTrue(shift.is_open)

        closed = self.client.post(
            reverse("pos:shift"),
            {"action": "close", "confirmation": "ЗАКРЫТЬ"},
        )
        self.assertRedirects(closed, reverse("pos:shift"))
        shift.refresh_from_db()
        order.refresh_from_db()
        self.assertFalse(shift.is_open)
        self.assertIsNone(shift.closed_at)
        self.assertEqual(shift.closed_by, self.user)
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)
        self.assertEqual(order.shift_id, shift.id)
        locked = self.client.get(reverse("pos:shift"))
        self.assertContains(locked, "Открыть смену")
        self.assertContains(locked, "Смена не открыта")


class StatsByShiftDateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cashier", password="pw")
        self.client.force_login(self.user)
        self.cat = Category.objects.create(
            name="Классика", slug="klassika", color="#2e78d9"
        )
        self.latte = Product.objects.create(
            name="Латте", price=Decimal("200"), category=self.cat
        )
        self.espresso = Product.objects.create(
            name="Эспрессо", price=Decimal("150"), category=self.cat
        )
        self.early = Shift.objects.create(business_date=date(2026, 10, 1), is_open=False)
        self.late = Shift.objects.create(
            business_date=date(2026, 10, 5), is_open=True, opened_by=self.user
        )
        morning = services.create_order()
        services.add_line(morning, self.latte, quantity=2)
        morning.shift = self.early
        services.pay_order(morning)
        services.mark_ready(morning)

        evening = services.create_order()
        services.add_line(evening, self.espresso, quantity=1)
        evening.shift = self.late
        services.pay_order(evening)
        services.mark_ready(evening)

        dropped = services.create_order()
        services.add_line(dropped, self.espresso, quantity=1)
        dropped.shift = self.late
        services.pay_order(dropped)
        services.cancel_order(dropped)

    def test_this_shift_ignores_other_business_dates(self):
        response = self.client.get(reverse("pos:stats") + "?period=this")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Эспрессо")
        self.assertNotContains(response, "Латте")
        self.assertContains(response, "150 ₽")
        self.assertContains(response, "Выгрузить CSV")
        self.assertEqual(response.context["stats"]["issued"], 1)
        self.assertEqual(response.context["stats"]["cancelled"], 1)
        self.assertEqual(response.context["stats"]["revenue"], Decimal("150.00"))
        points = response.context["chart"]["points"]
        self.assertEqual(
            [(point["label"], point["revenue"]) for point in points],
            [("5 окт", Decimal("150.00"))],
        )
        self.assertContains(response, 'class="revenue-chart"')
        self.assertContains(response, "5 окт")
        self.assertNotIn(",", response.content.decode().split('class="revenue-chart"', 1)[1].split("</svg>", 1)[0])

    def test_date_range_uses_shift_business_date(self):
        url = reverse("pos:stats") + "?from=2026-10-01&to=2026-10-01"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Латте")
        self.assertNotContains(response, "Эспрессо")
        self.assertEqual(response.context["stats"]["revenue"], Decimal("400.00"))
        self.assertEqual(response.context["stats"]["issued"], 1)
        self.assertEqual(response.context["stats"]["cancelled"], 0)
        self.assertEqual(
            [(point["label"], point["revenue"]) for point in response.context["chart"]["points"]],
            [("1 окт", Decimal("400.00"))],
        )

        everything = self.client.get(reverse("pos:stats") + "?period=all")
        self.assertEqual(
            [(point["label"], point["revenue"]) for point in everything.context["chart"]["points"]],
            [("1 окт", Decimal("400.00")), ("5 окт", Decimal("150.00"))],
        )

        exported = self.client.get(reverse("pos:stats_csv") + "?from=2026-10-01&to=2026-10-01")
        body = exported.content.decode("utf-8-sig")
        self.assertIn("2026-10-01", body)
        self.assertIn("Время оплаты", body)
        self.assertIn("Время выдачи", body)
        self.assertIn("Латте", body)
        self.assertNotIn("Эспрессо", body)
        self.assertNotIn("2026-10-05", body)

    def test_cards_panel_csv_and_load_chart_use_the_shift_clock(self):
        opened = datetime(2010, 1, 1, 3, 0, tzinfo=dt_timezone.utc)
        self.late.start_time = time(19, 30)
        self.late.opened_at = opened
        self.late.save(update_fields=["start_time", "opened_at"])
        evening = Order.objects.get(shift=self.late, status=Order.Status.READY)
        evening.guest_name = "Маша"
        evening.paid_at = opened + timedelta(minutes=17)
        evening.ready_at = opened + timedelta(minutes=40)
        evening.save(update_fields=["guest_name", "paid_at", "ready_at"])
        dropped = Order.objects.get(shift=self.late, status=Order.Status.CANCELLED)
        dropped.paid_at = opened + timedelta(minutes=45)
        dropped.save(update_fields=["paid_at"])

        queue = self.client.get(reverse("pos:queue_fragment"))
        self.assertContains(queue, "оплата 19:47")
        self.assertContains(queue, "выдан 20:10")
        self.assertNotContains(queue, "03:17")
        self.assertNotContains(queue, "2010")

        self.client.get(reverse("pos:queue_open", args=[evening.id]))
        panel = self.client.get(reverse("pos:order_panel"))
        self.assertContains(panel, "Оплата 19:47")
        self.assertContains(panel, "Выдан 20:10")

        stats = self.client.get(reverse("pos:stats") + "?period=this")
        self.assertContains(stats, "Нагрузка по времени")
        self.assertContains(stats, 'class="revenue-chart load-chart"')
        points = [
            (point["label"], point["value"])
            for point in stats.context["load_chart"]["points"]
        ]
        self.assertEqual(points, [("19:30", 1), ("20:00", 1)])
        svg = stats.content.decode().split('class="revenue-chart load-chart"', 1)[1].split("</svg>", 1)[0]
        self.assertNotIn(",", svg)
        self.assertIn("19:30", svg)

        other = self.client.get(reverse("pos:stats") + "?from=2026-10-01&to=2026-10-01")
        self.assertIsNone(other.context["load_chart"])

        exported = self.client.get(reverse("pos:stats_csv") + "?period=this")
        body = exported.content.decode("utf-8-sig")
        header = body.splitlines()[0]
        self.assertIn("Время оплаты", header)
        self.assertIn("Время выдачи", header)
        self.assertIn("19:47", body)
        self.assertIn("20:10", body)
        self.assertNotIn("03:17", body)

    def test_csv_has_a_takeaway_column(self):
        import csv
        import io

        evening = Order.objects.get(shift=self.late, status=Order.Status.READY)
        evening.guest_name = "Маша"
        evening.fulfilment = Order.Fulfilment.TO_GO
        evening.save(update_fields=["guest_name", "fulfilment"])
        dropped = Order.objects.get(shift=self.late, status=Order.Status.CANCELLED)
        dropped.guest_name = "Петя"
        dropped.save(update_fields=["guest_name"])

        exported = self.client.get(reverse("pos:stats_csv") + "?period=this")
        rows = list(csv.reader(io.StringIO(exported.content.decode("utf-8-sig"))))
        header = rows[0]
        self.assertIn("На вынос", header)
        takeaway = header.index("На вынос")
        guest = header.index("Гость")
        by_guest = {row[guest]: row[takeaway] for row in rows[1:]}
        self.assertEqual(by_guest["Маша"], "да")
        self.assertEqual(by_guest["Петя"], "нет")


class HandoutQueueScreenTests(TestCase):
    """Галочки, автоготово и переключение очередей на экране кассы."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="queue-cashier", password="cashier")
        cls.cat = Category.objects.create(name="Классика-очередь", slug="queue-klassika")
        cls.espresso = Product.objects.create(
            name="Эспрессо", price=Decimal("150"), category=cls.cat
        )
        cls.shift = Shift.objects.create(
            business_date=date(2026, 10, 5), is_open=True, opened_by=cls.user
        )

    def setUp(self):
        self.client.force_login(self.user)

    def _enqueue(self, name: str, *, pay: bool = True) -> Order:
        order = services.create_order(guest_name=name)
        services.add_line(order, self.espresso, quantity=1)
        if pay:
            services.pay_order(order)
        else:
            services.enqueue_order(order)
        order.refresh_from_db()
        return order

    def test_handout_checkbox_persists_and_does_not_open_the_editor(self):
        self.client.get(reverse("pos:register"))
        draft_id = self.client.session[SESSION_ORDER_KEY]
        order = self._enqueue("Маша")
        line = order.lines.get()

        response = self.client.post(reverse("pos:line_handed", args=[line.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="barista-queue"')
        self.assertNotContains(response, 'id="order-panel"')
        self.assertContains(response, 'aria-label="отдали"')
        self.assertContains(response, "is-handed")
        self.assertContains(response, "event.stopPropagation()")
        self.assertContains(response, "checked")
        line.refresh_from_db()
        self.assertTrue(line.handed_out)
        self.assertEqual(self.client.session[SESSION_ORDER_KEY], draft_id)

        again = self.client.post(reverse("pos:line_handed", args=[line.id]))
        self.assertNotContains(again, "is-handed")
        line.refresh_from_db()
        self.assertFalse(line.handed_out)

    def test_unpaid_card_uses_the_full_red_outline_class(self):
        self._enqueue("Квакша", pay=False)
        queue = self.client.get(reverse("pos:queue_fragment"))
        self.assertContains(queue, "q-card-unpaid")
        css = (Path(settings.BASE_DIR) / "static/css/app.css").read_text()
        rule = css.split(".q-card-unpaid", 1)[1].split("}", 1)[0]
        self.assertIn("border: 2px solid #c74747", rule)
        self.assertNotIn("inset", rule)

    def test_place_pills_show_on_every_queue_card(self):
        opened = datetime(2026, 10, 5, 16, 0, tzinfo=dt_timezone.utc)
        self.shift.opened_at = opened
        self.shift.start_time = time(19, 30)
        self.shift.save(update_fields=["opened_at", "start_time"])

        with patch("apps.orders.services.timezone.now", return_value=opened + timedelta(minutes=12)):
            here = self._enqueue("Взале")
            away = self._enqueue("Навынос")
            services.update_order_meta(away, fulfilment=Order.Fulfilment.TO_GO)
            ready = self._enqueue("Готовый")
            services.update_order_meta(ready, fulfilment=Order.Fulfilment.TO_GO)
            services.mark_ready(ready)
            dropped = self._enqueue("Снятый", pay=False)
            services.cancel_order(dropped)
        Order.objects.filter(pk__in=[ready.pk, dropped.pk]).update(
            main_queue_until=datetime(2020, 1, 1, tzinfo=dt_timezone.utc)
        )

        active = self.client.get(reverse("pos:queue_fragment"))
        active_body = active.content.decode()

        def lead(name: str) -> str:
            marker = f'<span class="q-name">{name}</span>'
            start = active_body.index(marker)
            return active_body[start:active_body.index("q-pills", start)]

        here_lead = lead("Взале")
        away_lead = lead("Навынос")
        self.assertIn("place-pill-here", here_lead)
        self.assertIn('title="здесь"', here_lead)
        self.assertIn("☕", here_lead)
        self.assertIn("q-times", here_lead)
        self.assertLess(here_lead.index("place-pill-here"), here_lead.index("оплата"))
        self.assertIn("place-pill-to_go", away_lead)
        self.assertIn('title="на вынос"', away_lead)
        self.assertIn("🏃", away_lead)
        self.assertLess(away_lead.index("place-pill-to_go"), away_lead.index("оплата"))

        ready_queue = self.client.get(reverse("pos:queue_fragment") + "?queue=ready")
        self.assertContains(ready_queue, "Готовый")
        self.assertContains(ready_queue, "place-pill-to_go")
        self.assertContains(ready_queue, 'title="на вынос"')
        self.assertContains(ready_queue, "🏃")
        self.assertNotContains(ready_queue, "Взале")

        cancelled = self.client.get(reverse("pos:queue_fragment") + "?queue=cancelled")
        self.assertContains(cancelled, "Снятый")
        self.assertContains(cancelled, "place-pill-here")
        self.assertContains(cancelled, 'title="здесь"')
        self.assertContains(cancelled, "☕")
        self.assertNotContains(cancelled, "Навынос")

        css = (Path(settings.BASE_DIR) / "static/css/app.css").read_text()
        pill = css.split(".place-pill {", 1)[1].split("}", 1)[0]
        here_rule = css.split(".place-pill-here", 1)[1].split("}", 1)[0]
        away_rule = css.split(".place-pill-to_go", 1)[1].split("}", 1)[0]
        self.assertIn("font-size: 16px", pill)
        self.assertIn("border-radius: 999px", pill)
        self.assertIn("#e3f0c4", here_rule)
        self.assertIn("#d3e4f8", away_rule)

        services.hand_off(here)
        screen = self.client.get(reverse("orders:queue"))
        self.assertContains(screen, "Навынос")
        self.assertContains(screen, "Взале")
        self.assertContains(screen, "place-pill-to_go")
        self.assertContains(screen, "place-pill-here")
        self.assertContains(screen, 'title="на вынос"')
        self.assertContains(screen, 'title="здесь"')

    def test_queue_switch_scopes_to_the_shift_and_sorts_oldest_first(self):
        t0 = datetime(2026, 10, 7, 12, 0, tzinfo=dt_timezone.utc)
        self.shift.opened_at = t0 - timedelta(minutes=17)
        self.shift.start_time = time(19, 30)
        self.shift.save(update_fields=["opened_at", "start_time"])

        with patch("apps.orders.services.timezone.now", return_value=t0):
            older = self._enqueue("Старый")
            newer = self._enqueue("Новый")
            ready = self._enqueue("Готовенький")
            dropped = self._enqueue("Снятый", pay=False)
            services.mark_ready(ready)
            services.cancel_order(dropped)
        Order.objects.filter(pk=older.pk).update(created_at=t0)
        Order.objects.filter(pk=newer.pk).update(created_at=t0 + timedelta(minutes=3))
        Order.objects.filter(pk=ready.pk).update(created_at=t0 + timedelta(minutes=1))
        Order.objects.filter(pk=dropped.pk).update(created_at=t0 + timedelta(minutes=2))

        other = Shift.objects.create(business_date=date(2026, 1, 1), is_open=False)
        stranger = self._enqueue("Чужой")
        stranger.shift = other
        stranger.save(update_fields=["shift"])

        with patch(
            "apps.orders.services.timezone.now",
            return_value=t0 + timedelta(seconds=1),
        ):
            holding = self.client.get(reverse("pos:queue_fragment"))
        html = holding.content.decode()
        self.assertLess(html.index("Старый"), html.index("Готовенький"))
        self.assertLess(html.index("Готовенький"), html.index("Снятый"))
        self.assertLess(html.index("Снятый"), html.index("Новый"))
        self.assertNotIn("Чужой", html)
        self.assertContains(holding, 'class="queue-switch"')
        self.assertContains(holding, "Готовые")
        self.assertContains(holding, ">Отмена<")

        Order.objects.filter(pk__in=[ready.pk, dropped.pk]).update(
            main_queue_until=t0 - timedelta(seconds=1)
        )
        active = self.client.get(reverse("pos:queue_fragment"))
        self.assertContains(active, "Старый")
        self.assertContains(active, "Новый")
        self.assertNotContains(active, "Готовенький")
        self.assertNotContains(active, "Снятый")

        ready_page = self.client.get(reverse("pos:queue_fragment") + "?queue=ready")
        self.assertContains(ready_page, "Готовенький")
        self.assertContains(ready_page, 'data-queue="ready"')
        self.assertNotContains(ready_page, "Старый")
        self.assertNotContains(ready_page, "Снятый")

        cancelled_page = self.client.get(
            reverse("pos:queue_fragment") + "?queue=cancelled"
        )
        self.assertContains(cancelled_page, "Снятый")
        self.assertContains(cancelled_page, 'data-queue="cancelled"')
        self.assertNotContains(cancelled_page, "Готовенький")

    def test_auto_ready_survives_reload_and_writes_the_handout_clock(self):
        t0 = datetime(2026, 10, 7, 12, 0, tzinfo=dt_timezone.utc)
        self.shift.opened_at = t0 - timedelta(minutes=17)
        self.shift.start_time = time(19, 30)
        self.shift.save(update_fields=["opened_at", "start_time"])
        with patch("apps.orders.services.timezone.now", return_value=t0):
            order = self._enqueue("Маша")
            services.set_line_handed_out(order.lines.get(), True)

        with patch(
            "apps.orders.services.timezone.now",
            return_value=t0 + timedelta(seconds=4),
        ):
            waiting = self.client.get(reverse("pos:queue_fragment"))
        self.assertContains(waiting, "data-auto-ready-at")
        self.assertContains(waiting, "Не готово")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)

        due = t0 + timedelta(seconds=5)
        with patch("apps.orders.services.timezone.now", return_value=due):
            promoted = self.client.get(reverse("pos:queue_fragment"))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.READY)
        self.assertEqual(order.ready_at, due)
        self.assertContains(promoted, "Готово")
        self.assertContains(promoted, "выдан 19:47")
        self.assertContains(promoted, "data-leave-at")
        self.assertContains(promoted, "Маша")
