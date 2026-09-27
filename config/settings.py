"""
Настройки Django для POS-приложения CashMachine.

Проект собран как небольшой самодостаточный монолит. Его можно запускать
двумя способами: как обычное Django-приложение или как настольное
приложение под Windows (через :mod:`desktop.launcher` и PyInstaller).

Полезные переменные окружения:

``CASHMACHINE_SECRET_KEY``
    Переопределяет стандартный (незащищённый) секретный ключ разработки.
``CASHMACHINE_DEBUG``
    Значение ``"0"`` отключает режим ``DEBUG``.
``CASHMACHINE_DB_PATH``
    Явный путь к SQLite-базе. Если не задан, используется путь под
    пользовательской директорией, подходящей для текущей ОС.
``CASHMACHINE_ALLOWED_HOSTS``
    Список разрешённых хостов через запятую.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

SECRET_KEY = os.environ.get(
    "CASHMACHINE_SECRET_KEY",
    "django-insecure-cashmachine-dev-key-change-me-in-production",
)

DEBUG = os.environ.get("CASHMACHINE_DEBUG", "1") != "0"

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get(
        "CASHMACHINE_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0"
    ).split(",")
    if h.strip()
]


# ---------------------------------------------------------------------------
# Apps
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_htmx",
    "apps.accounts",
    "apps.catalog",
    "apps.orders",
    "apps.analytics",
    "apps.pos",
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.pos.context_processors.pos_globals",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def _default_db_path() -> Path:
    override = os.environ.get("CASHMACHINE_DB_PATH")
    if override:
        p = Path(override).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        app_dir = base / "CashMachine"
    elif sys.platform == "darwin":
        app_dir = Path.home() / "Library" / "Application Support" / "CashMachine"
    else:
        app_dir = Path.home() / ".local" / "share" / "cashmachine"

    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir / "cashmachine.sqlite3"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(_default_db_path()),
    }
}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "pos:register"
LOGOUT_REDIRECT_URL = "accounts:login"


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 3}},
]


# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = os.environ.get("CASHMACHINE_TIME_ZONE", "Europe/Moscow")
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_NAME = "cashmachine_sessionid"
CSRF_TRUSTED_ORIGINS = [
    "http://localhost", "http://127.0.0.1", "http://0.0.0.0",
]

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"
