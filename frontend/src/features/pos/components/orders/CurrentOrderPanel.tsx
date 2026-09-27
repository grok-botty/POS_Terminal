import {
  Box, Typography, List, ListItem, ListItemText,
  IconButton, Divider, Button, TextField
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import RemoveIcon from "@mui/icons-material/Remove";
import DragIndicatorIcon from "@mui/icons-material/DragIndicator";
import { usePosStore } from "../../store";
import { useRef } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

const money = (n: number) => new Intl.NumberFormat("ru-RU").format(n);

function SortableItem({
  id,
  children,
  disabled
}: {
  id: string;
  children: React.ReactNode;
  disabled: boolean;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id, disabled });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <Box ref={setNodeRef} style={style}>
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        {!disabled && (
          <Box
            {...attributes}
            {...listeners}
            sx={{
              cursor: 'grab',
              display: 'flex',
              alignItems: 'center',
              mr: 1,
              '&:active': { cursor: 'grabbing' }
            }}
          >
            <DragIndicatorIcon sx={{ color: 'action.disabled' }} />
          </Box>
        )}
        <Box sx={{ flex: 1 }}>
          {children}
        </Box>
      </Box>
    </Box>
  );
}

export function CurrentOrderPanel() {
  const orders = usePosStore((s) => s.orders);
  const currentOrderId = usePosStore((s) => s.currentOrderId);

  const setOrderName = usePosStore((s) => s.setOrderName);
  const setOrderComment = usePosStore((s) => s.setOrderComment);
  const toggleOrderPaid = usePosStore((s) => s.toggleOrderPaid);
  const moveToQueueAndCreateNew = usePosStore((s) => s.moveToQueueAndCreateNew);

  const incLine = usePosStore((s) => s.incLine);
  const decLine = usePosStore((s) => s.decLine);
  const cancelOrder = usePosStore((s) => s.cancelOrder);
  const reorderLines = usePosStore((s) => s.reorderLines);

  const orderNameInputRef = useRef<HTMLInputElement>(null);
  const orderCommentInputRef = useRef<HTMLInputElement>(null);

  const handleNameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      orderCommentInputRef.current?.focus();
    }
  };

  const handleMoveToQueue = () => {
    if (!current) return;
    moveToQueueAndCreateNew();
    setTimeout(() => {
      orderNameInputRef.current?.focus();
      orderNameInputRef.current?.select();
    }, 0);
  };

  const current = currentOrderId ? orders[currentOrderId] : null;
  const currentLines = current
    ? current.lineOrder.map(id => current.lines[id]).filter(Boolean)
    : [];
  const total = currentLines.reduce((sum, l) => sum + l.price * l.qty, 0);
  const isHandedOff = current?.status === "HANDOFF";

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id && current) {
      const oldIndex = currentLines.findIndex((l) => l.lineId === active.id);
      const newIndex = currentLines.findIndex((l) => l.lineId === over.id);

      const newOrder = arrayMove(currentLines, oldIndex, newIndex);
      const newLineIds = newOrder.map(l => l.lineId);

      reorderLines(current.id, newLineIds);
    }
  };

  return (
    <Box sx={{ p: 2, display: "flex", flexDirection: "column", height: "100%" }}>
      {current && (
        <Box sx={{ mb: 2 }}>
          <TextField
            fullWidth
            size="small"
            label="Название заказа"
            value={current.name}
            onChange={(e) => setOrderName(current.id, e.target.value)}
            onKeyDown={handleNameKeyDown}
            inputRef={orderNameInputRef}
            disabled={isHandedOff}
            sx={{ mb: 1 }}
          />
          <TextField
            fullWidth
            size="small"
            label="Комментарий"
            value={current.comment}
            onChange={(e) => setOrderComment(current.id, e.target.value)}
            inputRef={orderCommentInputRef}
            disabled={isHandedOff}
            multiline
            rows={2}
          />
        </Box>
      )}

      <Divider sx={{ mb: 1 }} />

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={currentLines.map(l => l.lineId)}
          strategy={verticalListSortingStrategy}
        >
          <List dense sx={{ flex: 1, overflow: "auto" }}>
            {currentLines.map((l) => (
              <SortableItem key={l.lineId} id={l.lineId} disabled={isHandedOff}>
                <ListItem
                  sx={{
                    pl: l.isAddon ? 4 : 2,
                  }}
                  secondaryAction={
                    !isHandedOff && (
                      <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                        <IconButton onClick={() => decLine(l.lineId)}><RemoveIcon /></IconButton>
                        <Typography sx={{ minWidth: 24, textAlign: "center" }}>{l.qty}</Typography>
                        <IconButton onClick={() => incLine(l.lineId)}><AddIcon /></IconButton>
                      </Box>
                    )
                  }
                >
                  <ListItemText
                    primary={
                      <Typography variant="body2" color={l.isAddon ? "text.secondary" : "text.primary"}>
                        {l.isAddon ? `+ ${l.name}` : l.name}
                      </Typography>
                    }
                    secondary={`${money(l.price)} × ${l.qty} = ${money(l.price * l.qty)}`}
                  />
                </ListItem>
              </SortableItem>
            ))}
            {currentLines.length === 0 && (
              <Typography sx={{ color: "text.secondary", p: 1 }}>
                Добавь товары справа
              </Typography>
            )}
          </List>
        </SortableContext>
      </DndContext>

      <Divider sx={{ my: 1 }} />

      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          p: 1,
          borderRadius: 1,
          cursor: current && !isHandedOff ? "pointer" : "default",
          bgcolor: current?.isPaid ? "success.light" : "transparent",
          transition: "background-color 0.2s",
          "&:hover": current && !isHandedOff ? { bgcolor: current.isPaid ? "success.main" : "action.hover" } : {},
        }}
        onClick={() => current && !isHandedOff && toggleOrderPaid(current.id)}
      >
        <Typography sx={{ flex: 1, fontWeight: 700 }}>
          {current?.isPaid ? "✓ Оплачено" : "Итого"}
        </Typography>
        <Typography sx={{ fontWeight: 800 }}>{money(total)}</Typography>
      </Box>

      <Box sx={{ display: "flex", gap: 1, mt: 1 }}>
        <Button
          fullWidth
          variant="outlined"
          color="error"
          onClick={() => current && cancelOrder(current.id)}
          disabled={!current || isHandedOff}
        >
          Удалить
        </Button>

        <Button
          fullWidth
          variant="contained"
          onClick={handleMoveToQueue}
          disabled={!current || !current.isPaid || isHandedOff}
        >
          В очередь
        </Button>
      </Box>
    </Box>
  );
}
