from django.db import models
from django.contrib.auth.hashers import make_password, check_password


class User(models.Model):
    ROLE_CHOICES = [
        ("admin", "Администратор"),
        ("user", "Пользователь"),
    ]

    username = models.CharField(max_length=150, unique=True, db_index=True)
    password_hash = models.CharField(max_length=255)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="user")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password_hash)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100, unique=True, db_index=True)
    order = models.IntegerField(default=0)
    is_addon = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "categories"
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    price = models.FloatField()
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="products"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "products"
        verbose_name = "Продукт"
        verbose_name_plural = "Продукты"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} - {self.price}₽"


class DailySummary(models.Model):
    date = models.CharField(max_length=10, unique=True, db_index=True)
    total_revenue = models.FloatField(default=0.0)
    total_orders = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "daily_summaries"
        verbose_name = "Дневная сводка"
        verbose_name_plural = "Дневные сводки"

    def __str__(self):
        return f"Сводка за {self.date}"


class Order(models.Model):
    order_id = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=255)
    comment = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50)
    total = models.FloatField()
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField()
    queued_at = models.DateTimeField(null=True, blank=True)  # Время попадания в очередь
    handoff_at = models.DateTimeField(null=True, blank=True)  # Время отдачи заказа
    daily_summary = models.ForeignKey(
        DailySummary, on_delete=models.CASCADE, related_name="orders"
    )

    class Meta:
        db_table = "orders"
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"

    def __str__(self):
        return f"Заказ {self.name} ({self.order_id})"


class OrderLine(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    product_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    price = models.FloatField()
    qty = models.IntegerField()

    class Meta:
        db_table = "order_lines"
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказов"

    def __str__(self):
        return f"{self.name} x{self.qty}"
