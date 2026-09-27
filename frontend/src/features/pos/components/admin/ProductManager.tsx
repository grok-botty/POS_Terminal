import {
  Box,
  Button,
  TextField,
  List,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Paper,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import SaveIcon from "@mui/icons-material/Save";
import CancelIcon from "@mui/icons-material/Cancel";
import { useState } from "react";
import { usePosStore } from "../../store";
import type { Product } from "../../types";
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
import { SortableProductItem } from "./SortableItems";

type ProductFormData = {
  name: string;
  price: string;
  category_id: string;
};

export function ProductManager() {
  const [editingProductId, setEditingProductId] = useState<number | string | null>(null);
  const [productForm, setProductForm] = useState<ProductFormData>({
    name: "",
    price: "",
    category_id: "",
  });
  const [localProducts, setLocalProducts] = useState<Product[]>([]);
  const [filterCategoryId, setFilterCategoryId] = useState<string>("all");

  const products = usePosStore((s) => s.products);
  const categories = usePosStore((s) => s.categories);
  const addProduct = usePosStore((s) => s.addProduct);
  const updateProduct = usePosStore((s) => s.updateProduct);
  const deleteProduct = usePosStore((s) => s.deleteProduct);

  // Sync local state with store
  if (localProducts.length === 0 && products.length > 0) {
    setLocalProducts(products);
  }
  if (products.length !== localProducts.length) {
    setLocalProducts(products);
  }

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleEditProduct = (product: Product) => {
    setEditingProductId(product.id);
    setProductForm({
      name: product.name,
      price: product.price.toString(),
      category_id: String(product.category_id),
    });
  };

  const handleSaveProduct = async () => {
    const price = parseFloat(productForm.price);
    const category_id = parseInt(productForm.category_id);
    if (!productForm.name || isNaN(price) || price < 0 || isNaN(category_id)) return;

    try {
      if (editingProductId) {
        await updateProduct(editingProductId, {
          name: productForm.name,
          price,
          category_id,
        });
      } else {
        await addProduct({
          name: productForm.name,
          price,
          category_id,
        });
      }

      setEditingProductId(null);
      setProductForm({ name: "", price: "", category_id: String(categories[0]?.id ?? "") });
    } catch {
      alert("Ошибка при сохранении продукта");
    }
  };

  const handleCancelProduct = () => {
    setEditingProductId(null);
    setProductForm({ name: "", price: "", category_id: String(categories[0]?.id ?? "") });
  };

  const handleDeleteProduct = async (id: number | string) => {
    if (confirm("Удалить этот продукт?")) {
      try {
        await deleteProduct(id);
      } catch {
        alert("Ошибка при удалении продукта");
      }
    }
  };

  const handleProductDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      setLocalProducts((items) => {
        const oldIndex = items.findIndex((item) => item.id === active.id);
        const newIndex = items.findIndex((item) => item.id === over.id);
        return arrayMove(items, oldIndex, newIndex);
      });
    }
  };

  // Фильтруем продукты по выбранной категории
  const filteredProducts = filterCategoryId === "all"
    ? localProducts
    : localProducts.filter(p => String(p.category_id) === filterCategoryId);

  return (
    <Box>
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          {editingProductId ? "Редактировать продукт" : "Добавить продукт"}
        </Typography>
        <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
          <TextField
            size="small"
            label="Название"
            value={productForm.name}
            onChange={(e) => setProductForm({ ...productForm, name: e.target.value })}
            sx={{ flex: "1 1 200px" }}
          />
          <TextField
            size="small"
            label="Цена"
            type="number"
            value={productForm.price}
            onChange={(e) => setProductForm({ ...productForm, price: e.target.value })}
            sx={{ flex: "1 1 120px" }}
          />
          <FormControl size="small" sx={{ flex: "1 1 150px" }}>
            <InputLabel>Категория</InputLabel>
            <Select
              value={productForm.category_id}
              label="Категория"
              onChange={(e) => setProductForm({ ...productForm, category_id: e.target.value })}
            >
              {categories.map((cat) => (
                <MenuItem key={cat.id} value={String(cat.id)}>
                  {cat.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Box sx={{ display: "flex", gap: 1 }}>
            <Button
              variant="contained"
              startIcon={editingProductId ? <SaveIcon /> : <AddIcon />}
              onClick={handleSaveProduct}
              disabled={!productForm.name || !productForm.price || !productForm.category_id}
            >
              {editingProductId ? "Сохранить" : "Добавить"}
            </Button>
            {editingProductId && (
              <Button variant="outlined" startIcon={<CancelIcon />} onClick={handleCancelProduct}>
                Отмена
              </Button>
            )}
          </Box>
        </Box>
      </Paper>

      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
        <Typography variant="h6">
          Список продуктов ({filteredProducts.length} из {localProducts.length})
        </Typography>
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Фильтр по категории</InputLabel>
          <Select
            value={filterCategoryId}
            label="Фильтр по категории"
            onChange={(e) => setFilterCategoryId(e.target.value)}
          >
            <MenuItem value="all">Все категории</MenuItem>
            {categories.map((cat) => (
              <MenuItem key={cat.id} value={String(cat.id)}>
                {cat.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>
      <Typography variant="caption" color="text.secondary" sx={{ mb: 2, display: "block" }}>
        Перетаскивайте продукты для изменения порядка отображения
      </Typography>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleProductDragEnd}>
        <SortableContext items={filteredProducts.map((p) => p.id)} strategy={verticalListSortingStrategy}>
          <List>
            {filteredProducts.map((product) => {
              const category = categories.find((c) => c.id === product.category_id);
              return (
                <SortableProductItem
                  key={product.id}
                  product={product}
                  category={category}
                  isEditing={editingProductId === product.id}
                  onEdit={() => handleEditProduct(product)}
                  onDelete={() => handleDeleteProduct(product.id)}
                />
              );
            })}
          </List>
        </SortableContext>
      </DndContext>
    </Box>
  );
}
