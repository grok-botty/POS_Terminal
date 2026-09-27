from django.urls import path

from . import views

app_name = "orders"


urlpatterns = [
    path("", views.queue, name="queue"),
    path("fragment/", views.queue_fragment, name="queue_fragment"),
    path("<int:pk>/ready/", views.action_ready, name="ready"),
    path("<int:pk>/handoff/", views.action_handoff, name="handoff"),
    path("<int:pk>/cancel/", views.action_cancel, name="cancel"),
    path("all-ready/", views.action_all_ready, name="all_ready"),
]
