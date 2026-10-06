"""Тесты экрана кассы: допы, очередь и цикл статуса."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Category, Modifier, ModifierGroup, Product
from apps.orders import services
from apps.orders.models import Order, Shift
from apps.pos.views import FUNNY_GUESTS


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
        self.assertContains(response, 'name="to_go" checked')
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
        self.assertRedirects(
            self.client.get(reverse("pos:stats")), reverse("pos:shift")
        )

    def test_open_shift_keeps_the_posted_date(self):
        response = self.client.post(
            reverse("pos:shift"),
            {"action": "open", "business_date": "2020-01-02"},
        )
        self.assertRedirects(response, reverse("pos:register"))
        shift = Shift.objects.get()
        self.assertEqual(shift.business_date, date(2020, 1, 2))
        self.assertTrue(shift.is_open)
        self.assertIsNone(shift.opened_at)
        self.assertEqual(shift.opened_by, self.user)
        self.assertEqual(shift.cashier_name, "cashier")
        self.assertNotEqual(shift.business_date, date(2026, 10, 6))

        Shift.objects.all().delete()
        response = self.client.post(reverse("pos:shift"), {"action": "open"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Укажите дату смены")
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
        self.assertRedirects(guest.get(reverse("pos:stats")), reverse("pos:shift"))

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
        self.assertIn("Латте", body)
        self.assertNotIn("Эспрессо", body)
        self.assertNotIn("2026-10-05", body)
