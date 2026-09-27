import sys
import os
import threading
import time
import webbrowser
import urllib.request
from pathlib import Path

# Для PyInstaller: добавляем путь к упакованным модулям
if getattr(sys, "frozen", False):
    # Если запущено из PyInstaller
    bundle_dir = sys._MEIPASS
    sys.path.insert(0, bundle_dir)
else:
    # Если запущено напрямую
    bundle_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, bundle_dir)

HOST = os.getenv("HOST", "127.0.0.1")  # 127.0.0.1 для локального, 0.0.0.0 для облака
PORT = int(os.getenv("PORT", "8000"))  # 8000 для локального


def wait_until_ready(url: str, timeout_sec: float = 10.0) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as r:
                return 200 <= r.status < 500
        except Exception:
            time.sleep(0.2)
    return False


def run_django_server():
    """Запускает Django сервер в отдельном потоке"""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

    import django

    django.setup()

    # Применяем миграции при первом запуске
    from django.core.management import call_command
    from django.db import connection

    try:
        # Проверяем, существует ли таблица users
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
            )
            table_exists = cursor.fetchone() is not None

        if not table_exists:
            # Если таблиц нет, создаём их через migrate
            print("🔧 Создание таблиц базы данных...")
            call_command("migrate", "--run-syncdb", verbosity=1)
            print("✅ База данных инициализирована")
        else:
            # Если таблицы есть, просто применяем миграции
            print("🔧 Применение миграций...")
            call_command("migrate", verbosity=1)
            print("✅ Миграции применены")

        from app.init_db import init_database

        init_database()
    except Exception as e:
        print(f"⚠️  Ошибка при инициализации БД: {e}")
        import traceback

        traceback.print_exc()

    # Запускаем сервер
    from django.core.management import execute_from_command_line

    execute_from_command_line(
        ["manage.py", "runserver", f"{HOST}:{PORT}", "--noreload", "--nothreading"]
    )


def run():
    try:
        print("🚀 Запуск CashMachine...")
        print(f"📍 Сервер будет доступен по адресу: http://{HOST}:{PORT}/")

        # Запускаем Django сервер в отдельном потоке
        t = threading.Thread(target=run_django_server, daemon=True)
        t.start()

        # Ждём, пока сервер поднимется
        print("⏳ Ожидание запуска сервера...")
        health_url = f"http://{HOST}:{PORT}/api/health"
        if not wait_until_ready(health_url, timeout_sec=10):
            print("❌ Сервер не запустился в течение 10 секунд.")
            print("Нажмите Enter для выхода...")
            input()
            return

        print("✅ Сервер запущен успешно!")
        print("🌐 Открываем браузер...")

        # Открываем браузер
        webbrowser.open(f"http://{HOST}:{PORT}/")

        print("\n" + "=" * 50)
        print("CashMachine работает!")
        print(f"Адрес: http://{HOST}:{PORT}/")
        print("Для остановки нажмите Ctrl+C или закройте это окно")
        print("=" * 50 + "\n")

        try:
            # Держим процесс живым
            while t.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n⏹️  Завершение работы...")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback

        traceback.print_exc()
        print("\nНажмите Enter для выхода...")
        input()


if __name__ == "__main__":
    run()
