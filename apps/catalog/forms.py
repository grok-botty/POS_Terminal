"""Формы менеджерских разделов приложения :mod:`catalog`.

Формы намеренно тонкие: ModelForm-ы с подсказками и без лишней валидации.
Slug генерится автоматически на уровне модели, поэтому в форме он не
обязателен.
"""

from __future__ import annotations

from django import forms

from .models import Category, Modifier, ModifierGroup, Product


class _StyledForm(forms.ModelForm):
    """Общий предок: подмешивает CSS-классы к штатным Django-виджетам."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                continue
            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} form-control".strip()


class CategoryForm(_StyledForm):
    """Категория (вкладка на экране кассы)."""

    class Meta:
        model = Category
        fields = ("name", "slug", "order", "color", "is_active")
        widgets = {
            "color": forms.TextInput(attrs={"type": "color"}),
        }
        help_texts = {
            "slug": "Если пусто, сгенерируется автоматически из названия.",
            "order": "Меньшее значение — раньше в списке.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


class ProductForm(_StyledForm):
    """Товар меню."""

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
        help_texts = {
            "modifier_groups": "Опции, которые кассир сможет выбрать при добавлении.",
            "order": "Меньшее значение — раньше в сетке.",
        }


class ModifierGroupForm(_StyledForm):
    """Группа модификаторов (например, «Молоко» или «Сиропы»)."""

    class Meta:
        model = ModifierGroup
        fields = ("name", "slug", "selection_mode", "is_required", "order")
        help_texts = {
            "slug": "Если пусто, сгенерируется автоматически из названия.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


class ModifierForm(_StyledForm):
    """Одна опция внутри группы (например, «Овсяное»)."""

    class Meta:
        model = Modifier
        fields = ("group", "name", "price_delta", "is_active", "order")
        help_texts = {
            "price_delta": "Может быть отрицательным — тогда это скидка.",
        }
