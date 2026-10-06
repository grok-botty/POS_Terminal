"""Тесты экрана кассы: допы, очередь и цикл статуса."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Category, Modifier, ModifierGroup, Product
from apps.orders import services
from apps.orders.models import Order
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

    def setUp(self):
        self.client.force_login(self.user)

    def test_register_shows_shared_bar_and_sections(self):
        response = self.client.get(reverse("pos:register"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Очередь")
        self.assertContains(response, ">Все<")
        self.assertContains(response, "—— Классика ——")
        self.assertContains(response, "—— Еда ——")
        self.assertContains(response, "допы →")
        self.assertContains(response, "Оплатить · 1 клик")
        self.assertContains(response, 'href="/catalog/"')
        order = Order.objects.get(status=Order.Status.NEW)
        self.assertIn(order.guest_name, FUNNY_GUESTS)
        self.assertContains(response, order.guest_name)

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
