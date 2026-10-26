"""Вход без формы: касса сразу работает от демо-администратора."""

from __future__ import annotations

from django.contrib.auth import (
    BACKEND_SESSION_KEY,
    HASH_SESSION_KEY,
    SESSION_KEY,
    get_user_model,
    login,
)

# Один бэкенд в настройках; login() без этого аргумента тоже его найдёт,
# но явный путь не зависит от числа бэкендов.
_BACKEND = "django.contrib.auth.backends.ModelBackend"


class AutoAdminMiddleware:
    """Подставить сессию ``admin``, если посетитель ещё не вошёл.

    Страница пароля для повседневной кассы не нужна: аноним получает
    права менеджера (меню и статистика). Уже выбранный пользователь
    не подменяется.

    ``login()`` крутит ключ сессии (``cycle_key``): удаляет строку
    ``django_session`` и вставляет новую. На каждом опросе очереди это
    пишет в SQLite и ловит ``database is locked`` / ``SessionInterrupted``.
    Поэтому залогиненного пользователя не трогаем совсем. ``login()``
    вызывается только когда сессии ещё нет. Если cookie уже есть, но
    пользователя в ней нет, id дописывается в ту же строку.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ""
        if not path.startswith("/static/") and not _is_authenticated(request):
            _attach_demo_admin(request)
        return self.get_response(request)


def _is_authenticated(request) -> bool:
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated)


def _attach_demo_admin(request) -> None:
    """Записать демо-админа в сессию, не ротируя уже существующий ключ."""
    user = _demo_admin()
    if user is None:
        return
    session_uid = request.session.get(SESSION_KEY)
    if session_uid is not None and str(session_uid) != str(user.pk):
        return
    if request.session.session_key:
        _stamp_user(request, user)
        return
    login(request, user, backend=_BACKEND)


def _stamp_user(request, user) -> None:
    """Положить пользователя в текущую сессию без ``cycle_key``."""
    request.session[SESSION_KEY] = user._meta.pk.value_to_string(user)
    request.session[BACKEND_SESSION_KEY] = _BACKEND
    request.session[HASH_SESSION_KEY] = user.get_session_auth_hash()
    user.backend = _BACKEND
    request.user = user


def _demo_admin():
    User = get_user_model()
    user = User.objects.filter(username="admin").first()
    if user is not None:
        return user
    user = User.objects.create_user(username="admin", password="admin", role=User.ROLE_ADMIN)
    user.is_staff = True
    user.is_superuser = True
    user.save(update_fields=["is_staff", "is_superuser"])
    return user
