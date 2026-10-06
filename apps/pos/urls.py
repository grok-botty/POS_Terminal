from django.urls import path

from . import views

app_name = "pos"


urlpatterns = [
    path("", views.register, name="register"),
    path("shift/", views.shift_screen, name="shift"),
    path("stats/", views.stats, name="stats"),
    path("stats/export/", views.stats_csv, name="stats_csv"),
    path("panel/", views.order_panel, name="order_panel"),
    path("queue/", views.queue_fragment, name="queue_fragment"),
    path("queue/<int:pk>/", views.queue_open, name="queue_open"),
    path("queue/<int:pk>/cycle/", views.queue_cycle, name="queue_cycle"),
    path("queue/<int:pk>/status/", views.queue_set_status, name="queue_status"),
    path("products/", views.products_grid, name="products_grid"),
    path("products/<int:product_id>/pick/", views.modifier_picker, name="modifier_picker"),
    path("products/<int:product_id>/add/", views.add_line, name="add_line"),
    path("lines/<int:line_id>/edit/", views.line_edit, name="line_edit"),
    path("lines/<int:line_id>/inc/", views.line_inc, name="line_inc"),
    path("lines/<int:line_id>/dec/", views.line_dec, name="line_dec"),
    path("lines/<int:line_id>/remove/", views.line_remove, name="line_remove"),
    path("meta/", views.order_meta, name="order_meta"),
    path("pay/", views.order_pay, name="order_pay"),
    path("enqueue/", views.order_enqueue, name="order_enqueue"),
    path("discard/", views.order_discard, name="order_discard"),
]
