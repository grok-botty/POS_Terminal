"""Seed the catalog with a demo menu (idempotent)."""

from django.core.management.base import BaseCommand

from apps.catalog.services import seed_demo_menu


class Command(BaseCommand):
    help = "Заполнить меню демо-данными (только если каталог пуст)."

    def handle(self, *args, **options):
        seed_demo_menu()
        self.stdout.write(self.style.SUCCESS("Меню инициализировано."))
