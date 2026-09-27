from django import forms

from .models import Category, Modifier, ModifierGroup, Product


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "slug", "order", "color", "is_active")


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "name",
            "price",
            "category",
            "modifier_groups",
            "is_active",
            "order",
        )
        widgets = {
            "modifier_groups": forms.CheckboxSelectMultiple(),
        }


class ModifierGroupForm(forms.ModelForm):
    class Meta:
        model = ModifierGroup
        fields = ("name", "slug", "selection_mode", "is_required", "order")


class ModifierForm(forms.ModelForm):
    class Meta:
        model = Modifier
        fields = ("group", "name", "price_delta", "is_active", "order")
