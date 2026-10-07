"""Тесты менеджерских экранов приложения :mod:`catalog`.

Покрывают:

* доступ (кассир — 403, менеджер — 200, аноним — редирект на логин);
* создание/редактирование/удаление категорий, товаров, модификаторов;
* HTMX-переключение доступности (``is_active``) — возвращает фрагмент
  дашборда и меняет флаг в БД;
* автогенерация ``slug`` при пустом поле формы.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.catalog.models import Category, Modifier, ModifierGroup, Product
from apps.orders.models import Shift


def open_shift(user=None):
    """Касса и меню без открытой смены уводят на экран «Смена»."""
    return Shift.objects.create(
        business_date=date(2026, 10, 5), is_open=True, opened_by=user
    )


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

    def test_anonymous_reaches_the_menu_as_admin(self):
        response = self.client.get(reverse("catalog:dashboard"))
        self.assertRedirects(response, reverse("pos:shift"))
        open_shift()
        response = self.client.get(reverse("catalog:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Позиции")

    def test_cashier_forbidden(self):
        self.client.login(username="cash", password="pw")
        self.assertEqual(
            self.client.get(reverse("catalog:dashboard")).status_code, 403
        )
        self.assertEqual(
            self.client.get(reverse("catalog:product_create")).status_code, 403
        )
        self.assertEqual(self.client.get(reverse("catalog:groups")).status_code, 403)
        self.assertEqual(self.client.get(reverse("catalog:tags")).status_code, 403)
        response = self.client.post(
            reverse("catalog:category_toggle", args=[self.category.id])
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_allowed(self):
        self.client.login(username="mgr", password="pw")
        open_shift(self.manager)
        response = self.client.get(reverse("catalog:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Позиции")
        self.assertContains(response, "Редактирование")


class CatalogNavigationTests(TestCase):
    """Верхняя навигация не должна вести в /admin/ для обычных менеджеров."""

    def test_manager_without_shift_is_sent_to_open_it(self):
        User.objects.create_user(username="mgr", password="pw", role=User.ROLE_ADMIN)
        self.client.login(username="mgr", password="pw")
        response = self.client.get(reverse("catalog:dashboard"))
        self.assertRedirects(response, reverse("pos:shift"))

    def test_manager_topbar_hides_django_admin(self):
        user = User.objects.create_user(username="m", password="pw", role=User.ROLE_ADMIN)
        open_shift(user)
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
        open_shift(user)
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
        open_shift(self.manager)
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
        open_shift(self.manager)
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
        open_shift(self.manager)
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
        open_shift(self.manager)
        self.client.force_login(self.manager)
        response = self.client.get(reverse("catalog:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Латте")
        self.assertContains(response, "Скрытая позиция")
        self.assertContains(response, "в меню")
        self.assertContains(response, "скрыто")
        self.assertContains(response, "Показывать в кассе")
        self.assertContains(response, "/catalog/products/")


class MenuEditorTests(TestCase):
    """Редактор позиций и справочник групп допов."""

    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="mgr", password="pw", role=User.ROLE_ADMIN
        )
        cls.category = Category.objects.create(name="Классика", slug="klassika", order=1)
        cls.group = ModifierGroup.objects.create(
            name="Молоко", slug="milk", selection_mode=ModifierGroup.SELECTION_SINGLE
        )

    def setUp(self):
        open_shift(self.manager)
        self.client.login(username="mgr", password="pw")

    def test_create_product_attaches_group_and_shows_on_the_till(self):
        response = self.client.post(
            reverse("catalog:product_create"),
            data={
                "name": "Раф тыквенный",
                "price": "290",
                "category": self.category.id,
                "modifier_groups": [self.group.id],
                "is_active": "on",
                "order": 1,
                "stay": "1",
            },
        )
        product = Product.objects.get(name="Раф тыквенный")
        self.assertRedirects(
            response, reverse("catalog:dashboard") + f"?product={product.id}"
        )
        self.assertEqual(product.price, Decimal("290"))
        self.assertIn(self.group, product.modifier_groups.all())
        screen = self.client.get(reverse("pos:register"))
        self.assertContains(screen, "Раф тыквенный")
        self.assertContains(screen, "допы →")

    def test_group_editor_saves_priced_default_and_keeps_one_default(self):
        url = reverse("catalog:group_save_edit", args=[self.group.id])
        self.client.post(
            url,
            data={
                "name": "Молоко",
                "slug": "milk",
                "selection_mode": "single",
                "order": 1,
                "new_name": "обычное",
                "new_price": "0",
                "new_default": "on",
            },
        )
        plain = Modifier.objects.get(name="обычное")
        self.assertEqual(plain.price_delta, Decimal("0"))
        self.assertTrue(plain.is_default)

        self.client.post(
            url,
            data={
                "name": "Молоко",
                "slug": "milk",
                "selection_mode": "single",
                "order": 1,
                "option_id": [plain.id],
                f"name_{plain.id}": "обычное",
                f"price_{plain.id}": "0",
                "new_name": "овсяное",
                "new_price": "30",
                "new_default": "on",
            },
        )
        plain.refresh_from_db()
        oat = Modifier.objects.get(name="овсяное")
        self.assertEqual(oat.price_delta, Decimal("30.00"))
        self.assertTrue(oat.is_default)
        self.assertFalse(plain.is_default)

        page = self.client.get(reverse("catalog:groups") + f"?group={self.group.id}")
        self.assertContains(page, "овсяное")
        self.assertContains(page, "Один вариант")
        self.assertContains(page, "по умолчанию")

    def test_existing_group_options_do_not_require_reentering_its_name(self):
        """«Скидки» хранится со slug «скидки»; правка опций не требует названия заново."""
        created = self.client.post(
            reverse("catalog:group_save"),
            data={
                "name": "Скидки",
                "slug": "",
                "selection_mode": "multi",
                "order": 4,
            },
        )
        group = ModifierGroup.objects.get(name="Скидки")
        self.assertRedirects(
            created, reverse("catalog:groups") + f"?group={group.pk}"
        )
        self.assertEqual(group.slug, "скидки")

        edit = reverse("catalog:group_save_edit", args=[group.pk])
        added = self.client.post(
            edit,
            data={
                "name": group.name,
                "slug": group.slug,
                "selection_mode": "multi",
                "order": group.order,
                "new_name": "студент",
                "new_price": "-20",
            },
        )
        self.assertRedirects(added, reverse("catalog:groups") + f"?group={group.pk}")
        option = Modifier.objects.get(group=group, name="студент")
        self.assertEqual(option.price_delta, Decimal("-20"))

        edited = self.client.post(
            edit,
            data={
                "slug": group.slug,
                "selection_mode": "multi",
                "order": group.order,
                "option_id": [str(option.pk)],
                f"name_{option.pk}": "сотрудник",
                f"price_{option.pk}": "-30",
            },
        )
        self.assertRedirects(edited, reverse("catalog:groups") + f"?group={group.pk}")
        option.refresh_from_db()
        group.refresh_from_db()
        self.assertEqual(option.name, "сотрудник")
        self.assertEqual(option.price_delta, Decimal("-30"))
        self.assertEqual(group.name, "Скидки")

        deleted = self.client.post(
            reverse("catalog:modifier_delete", args=[option.pk]),
            data={"back": f"/catalog/groups/?group={group.pk}"},
        )
        self.assertRedirects(deleted, f"/catalog/groups/?group={group.pk}")
        self.assertFalse(Modifier.objects.filter(pk=option.pk).exists())
        group.refresh_from_db()
        self.assertEqual(group.name, "Скидки")

    def test_new_group_still_requires_a_name(self):
        before = ModifierGroup.objects.count()
        response = self.client.post(
            reverse("catalog:group_save"),
            data={
                "name": "   ",
                "slug": "",
                "selection_mode": "multi",
                "order": 0,
                "new_name": "не должна сохраниться",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Укажите название группы")
        self.assertEqual(ModifierGroup.objects.count(), before)
        self.assertFalse(
            Modifier.objects.filter(name="не должна сохраниться").exists()
        )
