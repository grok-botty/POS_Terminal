"""Идемпотентные помощники первого запуска.

Настольный лаунчер вызывает :func:`ensure_bootstrapped` при старте, чтобы
свежей установкой можно было пользоваться сразу, без ручного выполнения
management-команд. Функция:

1. Применяет ожидающие миграции.
2. Создаёт дефолтных пользователей ``admin/admin`` и ``cashier/cashier``,
   если таблица пользователей пуста.
3. Заполняет небольшое демо-меню, если каталог пуст.
"""

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import DEFAULT_DB_ALIAS, connections

log = logging.getLogger(__name__)


def _apply_migrations() -> None:
    call_command("migrate", verbosity=0, interactive=False)


def _ensure_default_users() -> None:
    User = get_user_model()
    if User.objects.exists():
        return
    admin = User.objects.create_user(
        username="admin", password="admin", role="admin"
    )
    admin.is_staff = True
    admin.is_superuser = True
    admin.save(update_fields=["is_staff", "is_superuser"])
    User.objects.create_user(username="cashier", password="cashier", role="cashier")
    log.info("Созданы дефолтные пользователи: admin/admin и cashier/cashier")


def _ensure_demo_menu() -> None:
    from apps.catalog.services import seed_demo_menu

    seed_demo_menu()


def ensure_bootstrapped() -> None:
    """Выполнить все шаги инициализации первого запуска."""
    connections.close_all()
    _apply_migrations()
    _ensure_default_users()
    _ensure_demo_menu()


def db_ready() -> bool:
    """Вернуть ``True``, если ORM может достучаться до базы данных."""
    try:
        conn = connections[DEFAULT_DB_ALIAS]
        conn.ensure_connection()
        return True
    except Exception:  # pragma: no cover - defensive
        return False
