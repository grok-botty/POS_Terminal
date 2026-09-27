"""Idempotent first-run initialisation: migrate + create defaults + seed menu."""

from django.core.management.base import BaseCommand

from apps.pos.bootstrap import ensure_bootstrapped


class Command(BaseCommand):
    help = "Применить миграции, создать дефолтных пользователей, заполнить меню."

    def handle(self, *args, **options):
        ensure_bootstrapped()
        self.stdout.write(self.style.SUCCESS(
            "База готова. Пользователи по умолчанию: admin/admin, cashier/cashier."
        ))
