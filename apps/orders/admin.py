from django.contrib import admin

from .models import Order, OrderLine, OrderLineModifier, Shift


class OrderLineModifierInline(admin.TabularInline):
    model = OrderLineModifier
    extra = 0
    readonly_fields = ("name_snapshot", "price_delta_snapshot")


class OrderLineInline(admin.TabularInline):
    model = OrderLine
    extra = 0
    readonly_fields = ("name_snapshot", "unit_price")


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ("business_date", "is_open", "opened_by", "closed_by")
    list_filter = ("is_open",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "short_code",
        "guest_name",
        "status",
        "fulfilment",
        "is_paid",
        "total_amount",
        "created_at",
    )
    list_filter = ("status", "is_paid", "fulfilment", "created_at")
    search_fields = ("short_code", "guest_name", "comment")
    inlines = [OrderLineInline]
    readonly_fields = ("total_amount", "paid_at", "ready_at", "handed_off_at")


@admin.register(OrderLine)
class OrderLineAdmin(admin.ModelAdmin):
    list_display = ("order", "name_snapshot", "unit_price", "quantity")
    inlines = [OrderLineModifierInline]
