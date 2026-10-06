"""Вход без формы: касса сразу работает от демо-администратора."""

from __future__ import annotations

from django.contrib.auth import get_user_model, login


class AutoAdminMiddleware:
    """Подставить сессию ``admin``, если посетитель ещё не вошёл.

    Страница пароля для повседневной кассы не нужна: аноним получает
    права менеджера (меню и статистика). Уже выбранный пользователь
    не подменяется.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ""
        if not path.startswith("/static/") and not request.user.is_authenticated:
            user = _demo_admin()
            if user is not None:
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return self.get_response(request)


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
