from django.urls import path

from . import views

app_name = "catalog"


urlpatterns = [
    path("", views.menu_dashboard, name="dashboard"),

    path("categories/new/", views.category_edit, name="category_create"),
    path("categories/<int:pk>/", views.category_edit, name="category_edit"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("categories/<int:pk>/toggle/", views.category_toggle, name="category_toggle"),

    path("products/new/", views.product_edit, name="product_create"),
    path("products/<int:pk>/", views.product_edit, name="product_edit"),
    path("products/<int:pk>/delete/", views.product_delete, name="product_delete"),
    path("products/<int:pk>/toggle/", views.product_toggle, name="product_toggle"),

    path("modifier-groups/new/", views.modifier_group_edit, name="mgroup_create"),
    path("modifier-groups/<int:pk>/", views.modifier_group_edit, name="mgroup_edit"),
    path(
        "modifier-groups/<int:pk>/delete/",
        views.modifier_group_delete,
        name="mgroup_delete",
    ),

    path("modifiers/new/", views.modifier_edit, name="modifier_create"),
    path("modifiers/<int:pk>/", views.modifier_edit, name="modifier_edit"),
    path("modifiers/<int:pk>/delete/", views.modifier_delete, name="modifier_delete"),
    path("modifiers/<int:pk>/toggle/", views.modifier_toggle, name="modifier_toggle"),
]
