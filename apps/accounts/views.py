from django.contrib.auth import login, logout
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from .forms import LoginForm


def login_view(request: HttpRequest) -> HttpResponse:
    """Отрисовать форму входа и авторизовать пользователя на POST-запросе."""
    if request.user.is_authenticated:
        return redirect("pos:register")

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.cleaned_data["user"])
        return redirect(request.GET.get("next") or "pos:register")
    return render(request, "accounts/login.html", {"form": form})


def logout_view(request: HttpRequest) -> HttpResponse:
    """Выйти из текущей сессии и вернуться на страницу входа."""
    logout(request)
    return redirect("accounts:login")
