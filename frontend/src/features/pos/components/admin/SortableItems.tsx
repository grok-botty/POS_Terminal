import { Box, IconButton, ListItem, ListItemText, Typography, Chip } from "@mui/material";
import DragIndicatorIcon from "@mui/icons-material/DragIndicator";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { Product, Category } from "../../types";

type SortableProductItemProps = {
  product: Product;
  category?: Category;
  isEditing: boolean;
  onEdit: () => void;
  onDelete: () => void;
};

export function SortableProductItem({
  product,
  category,
  isEditing,
  onEdit,
  onDelete,
}: SortableProductItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: product.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <ListItem
      ref={setNodeRef}
      style={style}
      sx={{
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 1,
        mb: 1,
        bgcolor: isEditing ? "action.selected" : "background.paper",
        cursor: isDragging ? "grabbing" : "default",
      }}
      secondaryAction={
        <Box>
          <IconButton edge="end" onClick={onEdit} sx={{ mr: 1 }}>
            <EditIcon />
          </IconButton>
          <IconButton edge="end" onClick={onDelete} color="error">
            <DeleteIcon />
          </IconButton>
        </Box>
      }
    >
      <IconButton
        {...attributes}
        {...listeners}
        sx={{ mr: 1, cursor: "grab", touchAction: "none" }}
      >
        <DragIndicatorIcon />
      </IconButton>
      <ListItemText
        primary={
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Typography variant="body1" sx={{ fontWeight: 500 }}>
              {product.name}
            </Typography>
            <Chip
              label={category?.name ?? "Без категории"}
              size="small"
              variant="outlined"
            />
          </Box>
        }
        secondary={`${product.price} ₽`}
      />
    </ListItem>
  );
}

type SortableCategoryItemProps = {
  category: Category;
  productCount: number;
  isEditing: boolean;
  onEdit: () => void;
  onDelete: () => void;
};

export function SortableCategoryItem({
  category,
  productCount,
  isEditing,
  onEdit,
  onDelete,
}: SortableCategoryItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: category.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <ListItem
      ref={setNodeRef}
      style={style}
      sx={{
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 1,
        mb: 1,
        bgcolor: isEditing ? "action.selected" : "background.paper",
        cursor: isDragging ? "grabbing" : "default",
      }}
      secondaryAction={
        <Box>
          <IconButton edge="end" onClick={onEdit} sx={{ mr: 1 }}>
            <EditIcon />
          </IconButton>
          <IconButton
            edge="end"
            onClick={onDelete}
            color="error"
            disabled={productCount > 0}
          >
            <DeleteIcon />
          </IconButton>
        </Box>
      }
    >
      <IconButton
        {...attributes}
        {...listeners}
        sx={{ mr: 1, cursor: "grab", touchAction: "none" }}
      >
        <DragIndicatorIcon />
      </IconButton>
      <ListItemText
        primary={
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Typography variant="body1" sx={{ fontWeight: 500 }}>
              {category.name}
            </Typography>
            <Chip
              label={`${productCount} товар(ов)`}
              size="small"
              color={productCount > 0 ? "primary" : "default"}
            />
          </Box>
        }
        secondary={`Slug: ${category.slug} • Порядок: ${category.order}${category.is_addon ? ' • Добавка' : ''}`}
      />
    </ListItem>
  );
}
