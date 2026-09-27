from django import forms
from django.contrib.auth import authenticate


class LoginForm(forms.Form):
    """Simple username + password form used by :func:`views.login_view`."""

    username = forms.CharField(
        label="Логин",
        max_length=150,
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def clean(self):
        cleaned = super().clean()
        username = cleaned.get("username")
        password = cleaned.get("password")
        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise forms.ValidationError("Неверный логин или пароль.")
            if not user.is_active:
                raise forms.ValidationError("Пользователь отключён.")
            cleaned["user"] = user
        return cleaned
