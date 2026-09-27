import {
  Box,
  Button,
  TextField,
  List,
  Typography,
  Paper,
  FormControlLabel,
  Checkbox,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import SaveIcon from "@mui/icons-material/Save";
import CancelIcon from "@mui/icons-material/Cancel";
import { useState } from "react";
import { usePosStore } from "../../store";
import type { Category } from "../../types";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import type { DragEndEvent } from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { SortableCategoryItem } from "./SortableItems";

type CategoryFormData = {
  name: string;
  slug: string;
  is_addon: boolean;
};

export function CategoryManager() {
  const [editingCategoryId, setEditingCategoryId] = useState<number | null>(null);
  const [categoryForm, setCategoryForm] = useState<CategoryFormData>({
    name: "",
    slug: "",
    is_addon: false,
  });
  const [localCategories, setLocalCategories] = useState<Category[]>([]);

  const products = usePosStore((s) => s.products);
  const categories = usePosStore((s) => s.categories);
  const addCategory = usePosStore((s) => s.addCategory);
  const updateCategory = usePosStore((s) => s.updateCategory);
  const deleteCategory = usePosStore((s) => s.deleteCategory);
  const reorderCategories = usePosStore((s) => s.reorderCategories);

  // Sync local state with store
  if (localCategories.length === 0 && categories.length > 0) {
    setLocalCategories([...categories].sort((a, b) => a.order - b.order));
  }
  if (categories.length !== localCategories.length) {
    setLocalCategories([...categories].sort((a, b) => a.order - b.order));
  }

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleEditCategory = (category: Category) => {
    setEditingCategoryId(category.id);
    setCategoryForm({
      name: category.name,
      slug: category.slug,
      is_addon: category.is_addon || false,
    });
  };

  const handleSaveCategory = async () => {
    if (!categoryForm.name || !categoryForm.slug) return;

    try {
      if (editingCategoryId) {
        await updateCategory(editingCategoryId, categoryForm.name, categoryForm.is_addon);
      } else {
        await addCategory(categoryForm.name, categoryForm.slug, categoryForm.is_addon);
      }

      setEditingCategoryId(null);
      setCategoryForm({ name: "", slug: "", is_addon: false });
    } catch {
      alert("Ошибка при сохранении категории");
    }
  };

  const handleCancelCategory = () => {
    setEditingCategoryId(null);
    setCategoryForm({ name: "", slug: "", is_addon: false });
  };

  const handleDeleteCategory = async (id: number) => {
    const productsInCategory = products.filter((p) => p.category_id === id);
    if (productsInCategory.length > 0) {
      alert(`Невозможно удалить категорию: в ней ${productsInCategory.length} товар(ов)`);
      return;
    }

    if (confirm("Удалить эту категорию?")) {
      try {
        await deleteCategory(id);
      } catch {
        alert("Ошибка при удалении категории");
      }
    }
  };

  const handleCategoryDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = localCategories.findIndex((item) => item.id === active.id);
      const newIndex = localCategories.findIndex((item) => item.id === over.id);
      const newOrder = arrayMove(localCategories, oldIndex, newIndex);

      setLocalCategories(newOrder);

      try {
        await reorderCategories(newOrder.map((c) => c.id));
      } catch {
        alert("Ошибка при изменении порядка категорий");
        setLocalCategories([...categories].sort((a, b) => a.order - b.order));
      }
    }
  };

  return (
    <Box>
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          {editingCategoryId ? "Редактировать категорию" : "Добавить категорию"}
        </Typography>
        <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
          <TextField
            size="small"
            label="Название"
            value={categoryForm.name}
            onChange={(e) => setCategoryForm({ ...categoryForm, name: e.target.value })}
            sx={{ flex: "1 1 200px" }}
          />
          <TextField
            size="small"
            label="Slug (латиница)"
            value={categoryForm.slug}
            onChange={(e) => setCategoryForm({ ...categoryForm, slug: e.target.value.toLowerCase() })}
            sx={{ flex: "1 1 200px" }}
            disabled={!!editingCategoryId}
            helperText={editingCategoryId ? "Slug нельзя изменить" : "Используется в URL"}
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={categoryForm.is_addon}
                onChange={(e) => setCategoryForm({ ...categoryForm, is_addon: e.target.checked })}
              />
            }
            label="Добавка"
            sx={{ flex: "0 0 auto" }}
          />
          <Box sx={{ display: "flex", gap: 1 }}>
            <Button
              variant="contained"
              startIcon={editingCategoryId ? <SaveIcon /> : <AddIcon />}
              onClick={handleSaveCategory}
              disabled={!categoryForm.name || !categoryForm.slug}
            >
              {editingCategoryId ? "Сохранить" : "Добавить"}
            </Button>
            {editingCategoryId && (
              <Button variant="outlined" startIcon={<CancelIcon />} onClick={handleCancelCategory}>
                Отмена
              </Button>
            )}
          </Box>
        </Box>
      </Paper>

      <Typography variant="h6" sx={{ mb: 2 }}>
        Список категорий ({localCategories.length})
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ mb: 2, display: "block" }}>
        Перетаскивайте категории для изменения порядка отображения
      </Typography>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleCategoryDragEnd}>
        <SortableContext items={localCategories.map((c) => c.id)} strategy={verticalListSortingStrategy}>
          <List>
            {localCategories.map((category) => {
              const productCount = products.filter((p) => p.category_id === category.id).length;
              return (
                <SortableCategoryItem
                  key={category.id}
                  category={category}
                  productCount={productCount}
                  isEditing={editingCategoryId === category.id}
                  onEdit={() => handleEditCategory(category)}
                  onDelete={() => handleDeleteCategory(category.id)}
                />
              );
            })}
          </List>
        </SortableContext>
      </DndContext>
    </Box>
  );
}
