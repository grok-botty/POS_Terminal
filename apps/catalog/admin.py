from django.contrib import admin

from .models import Category, Modifier, ModifierGroup, Product


class ModifierInline(admin.TabularInline):
    model = Modifier
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "is_active", "color")
    list_editable = ("order", "is_active", "color")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ModifierGroup)
class ModifierGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "selection_mode", "is_required", "order")
    list_editable = ("selection_mode", "is_required", "order")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ModifierInline]


@admin.register(Modifier)
class ModifierAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "price_delta", "is_active", "order")
    list_filter = ("group",)
    list_editable = ("price_delta", "is_active", "order")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "is_active", "order")
    list_filter = ("category", "is_active")
    list_editable = ("price", "is_active", "order")
    search_fields = ("name",)
    filter_horizontal = ("modifier_groups",)
