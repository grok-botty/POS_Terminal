"""Тесты менеджерских экранов приложения :mod:`catalog`.

Покрывают:

* доступ (кассир — 403, менеджер — 200, аноним — редирект на логин);
* создание/редактирование/удаление категорий, товаров, модификаторов;
* HTMX-переключение доступности (``is_active``) — возвращает фрагмент
  дашборда и меняет флаг в БД;
* автогенерация ``slug`` при пустом поле формы.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.catalog.models import Category, Modifier, ModifierGroup, Product


User = get_user_model()


class CatalogPermissionsTests(TestCase):
    """Только менеджеры допускаются в раздел управления меню."""

    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="mgr", password="pw", role=User.ROLE_ADMIN
        )
        cls.cashier = User.objects.create_user(
            username="cash", password="pw", role=User.ROLE_CASHIER
        )
        cls.category = Category.objects.create(
            name="Напитки", slug="drinks", order=1
        )

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("catalog:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_cashier_forbidden(self):
        self.client.login(username="cash", password="pw")
        self.assertEqual(
            self.client.get(reverse("catalog:dashboard")).status_code, 403
        )
        self.assertEqual(
            self.client.get(reverse("catalog:product_create")).status_code, 403
        )
        response = self.client.post(
            reverse("catalog:category_toggle", args=[self.category.id])
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_allowed(self):
        self.client.login(username="mgr", password="pw")
        response = self.client.get(reverse("catalog:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Управление меню")


class CatalogNavigationTests(TestCase):
    """Верхняя навигация не должна вести в /admin/ для обычных менеджеров."""

    def test_manager_topbar_hides_django_admin(self):
        user = User.objects.create_user(username="m", password="pw", role=User.ROLE_ADMIN)
        self.client.force_login(user)
        response = self.client.get(reverse("pos:register"))
        self.assertContains(response, 'href="/catalog/"')
        self.assertNotContains(response, 'href="/admin/"')

    def test_superuser_still_sees_django_admin(self):
        user = User.objects.create_user(
            username="root", password="pw", role=User.ROLE_ADMIN
        )
        user.is_superuser = True
        user.is_staff = True
        user.save()
        self.client.force_login(user)
        response = self.client.get(reverse("pos:register"))
        self.assertContains(response, 'href="/admin/"')


class ProductCrudTests(TestCase):
    """Полный цикл CRUD товара через менеджерские вьюхи."""

    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="mgr", password="pw", role=User.ROLE_ADMIN
        )
        cls.category = Category.objects.create(
            name="Напитки", slug="drinks", order=1
        )
        cls.group = ModifierGroup.objects.create(name="Молоко", slug="milk")

    def setUp(self):
        self.client.login(username="mgr", password="pw")

    def test_create_product_via_form(self):
        response = self.client.post(
            reverse("catalog:product_create"),
            data={
                "name": "Флэт уайт",
                "price": "230",
                "category": self.category.id,
                "modifier_groups": [self.group.id],
                "is_active": "on",
                "order": 5,
            },
        )
        self.assertRedirects(response, reverse("catalog:dashboard"))
        product = Product.objects.get(name="Флэт уайт")
        self.assertEqual(product.price, Decimal("230"))
        self.assertIn(self.group, product.modifier_groups.all())

    def test_edit_product_updates_price(self):
        product = Product.objects.create(
            name="Раф", price=Decimal("240"), category=self.category
        )
        response = self.client.post(
            reverse("catalog:product_edit", args=[product.id]),
            data={
                "name": "Раф",
                "price": "260",
                "category": self.category.id,
                "is_active": "on",
                "order": 0,
            },
        )
        self.assertRedirects(response, reverse("catalog:dashboard"))
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal("260"))

    def test_delete_product_removes_it(self):
        product = Product.objects.create(
            name="Матча", price=Decimal("260"), category=self.category
        )
        response = self.client.post(
            reverse("catalog:product_delete", args=[product.id])
        )
        self.assertRedirects(response, reverse("catalog:dashboard"))
        self.assertFalse(Product.objects.filter(pk=product.id).exists())

    def test_toggle_product_availability(self):
        product = Product.objects.create(
            name="Латте", price=Decimal("220"), category=self.category
        )
        self.assertTrue(product.is_active)
        response = self.client.post(
            reverse("catalog:product_toggle", args=[product.id])
        )
        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertFalse(product.is_active)
        # HTMX-фрагмент содержит корневой div дашборда.
        self.assertContains(response, 'id="catalog-dashboard"')

        self.client.post(reverse("catalog:product_toggle", args=[product.id]))
        product.refresh_from_db()
        self.assertTrue(product.is_active)

    def test_product_create_prefills_category_from_query(self):
        response = self.client.get(
            reverse("catalog:product_create") + f"?category={self.category.id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"].initial["category"], self.category.id
        )


class CategoryCrudTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="mgr", password="pw", role=User.ROLE_ADMIN
        )

    def setUp(self):
        self.client.login(username="mgr", password="pw")

    def test_create_category_generates_slug(self):
        response = self.client.post(
            reverse("catalog:category_create"),
            data={
                "name": "Выпечка",
                "slug": "",
                "order": 3,
                "color": "#ffb300",
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("catalog:dashboard"))
        cat = Category.objects.get(name="Выпечка")
        self.assertTrue(cat.slug)

    def test_toggle_category_visibility(self):
        cat = Category.objects.create(name="Напитки", slug="drinks", order=1)
        self.client.post(reverse("catalog:category_toggle", args=[cat.id]))
        cat.refresh_from_db()
        self.assertFalse(cat.is_active)


class ModifierCrudTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="mgr", password="pw", role=User.ROLE_ADMIN
        )
        cls.group = ModifierGroup.objects.create(name="Сиропы", slug="syrups")

    def setUp(self):
        self.client.login(username="mgr", password="pw")

    def test_create_modifier(self):
        response = self.client.post(
            reverse("catalog:modifier_create"),
            data={
                "group": self.group.id,
                "name": "Клубника",
                "price_delta": "40",
                "is_active": "on",
                "order": 4,
            },
        )
        self.assertRedirects(response, reverse("catalog:dashboard"))
        self.assertTrue(Modifier.objects.filter(name="Клубника").exists())

    def test_toggle_modifier(self):
        opt = Modifier.objects.create(
            group=self.group, name="Ваниль", price_delta=Decimal("30")
        )
        self.client.post(reverse("catalog:modifier_toggle", args=[opt.id]))
        opt.refresh_from_db()
        self.assertFalse(opt.is_active)

    def test_modifier_create_prefills_group_from_query(self):
        response = self.client.get(
            reverse("catalog:modifier_create") + f"?group={self.group.id}"
        )
        self.assertEqual(response.context["form"].initial["group"], self.group.id)


class DashboardRenderingTests(TestCase):
    """Дашборд отображает переключатели, кнопки и учитывает hidden-товары."""

    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="mgr", password="pw", role=User.ROLE_ADMIN
        )
        cat = Category.objects.create(name="Напитки", slug="drinks", order=1)
        Product.objects.create(name="Латте", price=Decimal("220"), category=cat)
        Product.objects.create(
            name="Скрытая позиция", price=Decimal("0"), category=cat, is_active=False
        )
        ModifierGroup.objects.create(name="Молоко", slug="milk")

    def test_dashboard_shows_products_and_toggle(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("catalog:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Латте")
        self.assertContains(response, "Скрытая позиция")
        # Кнопки-переключатели должны быть в разметке.
        self.assertContains(response, "В меню")
        self.assertContains(response, "Скрыт")
        self.assertContains(response, "switch-btn")
        # HTMX-эндпоинт переключения должен быть в разметке.
        self.assertContains(response, "/catalog/products/")
