"""Кастомная модель пользователя CashMachine.

Модель — лёгкое расширение
:class:`~django.contrib.auth.models.AbstractUser`. Это позволяет
пользоваться стандартной админкой Django, системой прав, группами и
хешированием паролей «из коробки», но при этом различать кассиров и
администраторов по роли.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Сотрудник, работающий за кассой.

    Пользователи со значением :attr:`role`, равным :attr:`ROLE_ADMIN`,
    дополнительно могут править меню и смотреть аналитику; обычные
    пользователи могут только принимать заказы и закрывать смену.
    """

    ROLE_ADMIN = "admin"
    ROLE_CASHIER = "cashier"
    ROLE_CHOICES = (
        (ROLE_ADMIN, "Администратор"),
        (ROLE_CASHIER, "Кассир"),
    )

    role = models.CharField(
        "Роль",
        max_length=16,
        choices=ROLE_CHOICES,
        default=ROLE_CASHIER,
        help_text="Определяет доступ к настройкам меню и аналитике.",
    )

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def is_manager(self) -> bool:
        """Вернуть ``True``, если у пользователя есть доступ к разделам управления."""
        return self.is_superuser or self.role == self.ROLE_ADMIN

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.get_username()
