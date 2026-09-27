"""
Django settings for CashMachine project.
"""

import os
import sys
from pathlib import Path

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-cash-machine-local-dev-key-change-in-production"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["*"]

# Application definition
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
    "app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "app.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "app.wsgi.application"

# Database
# Используем переменную окружения для пути к БД или дефолтную директорию
if os.getenv("DOCKER_ENV"):
    # В Docker используем /data
    DB_PATH = Path("/data/pos.sqlite")
else:
    # Локально используем домашнюю директорию
    if os.name == "nt":  # Windows
        APP_DIR = Path.home() / "AppData" / "Local" / "MyPOS"
    elif sys.platform == "darwin":  # macOS
        APP_DIR = Path.home() / "Library" / "Application Support" / "MyPOS"
    else:  # Linux
        APP_DIR = Path.home() / ".local" / "share" / "MyPOS"

    APP_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH = APP_DIR / "pos.sqlite"

# Создаём родительскую директорию если нужно
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DB_PATH,
    }
}

# Internationalization
LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS settings (для работы с фронтендом)
CORS_ALLOW_ALL_ORIGINS = True
CSRF_TRUSTED_ORIGINS = ["http://localhost:*", "http://127.0.0.1:*"]

# Отключаем CSRF для API (так как это SPA приложение)
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
