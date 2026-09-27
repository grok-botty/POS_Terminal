"""Idempotent first-run helpers.

The desktop launcher calls :func:`ensure_bootstrapped` on start-up so that a
fresh install can be used immediately without running any management
commands.  It:

1. Applies pending migrations.
2. Creates a default ``admin/admin`` and ``cashier/cashier`` user if the user
   table is empty.
3. Seeds a small demo menu if the catalog is empty.
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
    log.info("Created default users: admin/admin and cashier/cashier")


def _ensure_demo_menu() -> None:
    from apps.catalog.services import seed_demo_menu

    seed_demo_menu()


def ensure_bootstrapped() -> None:
    """Run all first-launch initialisation steps."""
    connections.close_all()
    _apply_migrations()
    _ensure_default_users()
    _ensure_demo_menu()


def db_ready() -> bool:
    """Return ``True`` if the ORM can talk to the database."""
    try:
        conn = connections[DEFAULT_DB_ALIAS]
        conn.ensure_connection()
        return True
    except Exception:  # pragma: no cover - defensive
        return False
