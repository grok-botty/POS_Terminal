from django.urls import path

from . import views

app_name = "analytics"


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("close-day/", views.close_day_view, name="close_day"),
]
