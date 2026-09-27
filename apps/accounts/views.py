from django.contrib.auth import login, logout
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from .forms import LoginForm


def login_view(request: HttpRequest) -> HttpResponse:
    """Render the login form and authenticate the user on POST."""
    if request.user.is_authenticated:
        return redirect("pos:register")

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.cleaned_data["user"])
        return redirect(request.GET.get("next") or "pos:register")
    return render(request, "accounts/login.html", {"form": form})


def logout_view(request: HttpRequest) -> HttpResponse:
    """Log the current user out and redirect to the login page."""
    logout(request)
    return redirect("accounts:login")
