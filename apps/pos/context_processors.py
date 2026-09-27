"""Template context processors used across the POS UI."""

from __future__ import annotations

from django.http import HttpRequest


def pos_globals(request: HttpRequest) -> dict:
    """Expose commonly-used flags to every template."""
    user = getattr(request, "user", None)
    return {
        "is_manager": bool(user and user.is_authenticated and user.is_manager()),
        "app_name": "CashMachine · Касса 6ки",
    }
