from django.contrib import admin

from .models import DailySummary


@admin.register(DailySummary)
class DailySummaryAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "total_revenue",
        "total_orders",
        "paid_orders",
        "unpaid_orders",
        "avg_check",
        "closed_by",
        "closed_at",
    )
    readonly_fields = ("closed_at",)
    date_hierarchy = "date"
