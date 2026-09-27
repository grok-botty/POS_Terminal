"""Custom user model for the CashMachine POS.

The project uses a lightweight extension of :class:`~django.contrib.auth.models.AbstractUser`
so the standard Django admin, permissions, groups and password hashing all work
out of the box while still allowing a role-based distinction between cashiers
and administrators.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """A staff member who can operate the register.

    Users with :attr:`role` set to :attr:`ROLE_ADMIN` can also manage the menu
    and see analytics; regular users can only take orders and close the day.
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
        """Return ``True`` if the user can access management screens."""
        return self.is_superuser or self.role == self.ROLE_ADMIN

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.get_username()
