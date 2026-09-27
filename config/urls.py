"""Root URL configuration.

Each Django app owns its own :mod:`urls` module which is included here under a
namespace matching the app label.
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView


urlpatterns = [
    path("", RedirectView.as_view(pattern_name="pos:register", permanent=False)),
    path("pos/", include(("apps.pos.urls", "pos"), namespace="pos")),
    path("accounts/", include(("apps.accounts.urls", "accounts"), namespace="accounts")),
    path("catalog/", include(("apps.catalog.urls", "catalog"), namespace="catalog")),
    path("orders/", include(("apps.orders.urls", "orders"), namespace="orders")),
    path("analytics/", include(("apps.analytics.urls", "analytics"), namespace="analytics")),
    path("admin/", admin.site.urls),
]
