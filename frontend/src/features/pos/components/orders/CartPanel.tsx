import {
  Box, Paper, Typography, List, ListItem,
  IconButton, ToggleButton, ToggleButtonGroup,
  Button
} from "@mui/material";
import InfoIcon from "@mui/icons-material/Info";
import { usePosStore } from "../../store";
import { OrderCard } from "./OrderCard";
import { OrderTimer } from "./OrderTimer";
import { EndDayButton } from "../shared/EndDayButton";
import { useState, useEffect, useRef } from "react";

const money = (n: number) => new Intl.NumberFormat("ru-RU").format(n);

export function CartPanel() {
  const statusFilter = usePosStore((s) => s.statusFilter);
  const setStatusFilter = usePosStore((s) => s.setStatusFilter);

  const orders = usePosStore((s) => s.orders);
  const currentOrderId = usePosStore((s) => s.currentOrderId);
  const selectOrder = usePosStore((s) => s.selectOrder);
  const setOrderStatus = usePosStore((s) => s.setOrderStatus);

  const [viewOrder, setViewOrder] = useState<string | null>(null);
  const [handoffOrderId, setHandoffOrderId] = useState<string | null>(null);
  const handoffButtonRef = useRef<HTMLButtonElement>(null);

  const handleDoubleClick = (orderId: string) => {
    if (statusFilter === "NEW") {
      const order = orders[orderId];
      // Показываем кнопку только если заказ оплачен
      if (order?.isPaid) {
        setHandoffOrderId(orderId);
      }
    }
  };

  const handleHandoff = (orderId: string) => {
    const order = orders[orderId];
    // Дополнительная проверка перед отправкой
    if (order?.isPaid) {
      setOrderStatus(orderId, "HANDOFF");
      setHandoffOrderId(null);
    }
  };

  // Закрываем кнопку "Отдать" при клике вне её
  useEffect(() => {
    if (!handoffOrderId) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (handoffButtonRef.current && !handoffButtonRef.current.contains(event.target as Node)) {
        setHandoffOrderId(null);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [handoffOrderId]);

  const filteredOrders = Object.values(orders)
    .filter((o) => o.status === statusFilter)
    .sort((a, b) => a.createdAt - b.createdAt); // Сортировка от старого к новому

  return (
    <Box sx={{ height: "100vh", p: 2, display: "flex", flexDirection: "column", gap: 2 }}>
      {/* Список заказов */}
      <Paper variant="outlined" sx={{ p: 2, overflow: "auto", flex: 1 }}>
        <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 700 }}>
          {statusFilter === "NEW" ? "Очередь" : "Выдано"}
        </Typography>

        <List dense>
          {filteredOrders.map((o) => {
            const orderLines = o.lineOrder.map(id => o.lines[id]).filter(Boolean);
            const orderTotal = orderLines.reduce((sum, l) => sum + l.price * l.qty, 0);

            return (
              <Box key={o.id} sx={{ mb: 1 }}>
                {handoffOrderId === o.id ? (
                  <Button
                    ref={handoffButtonRef}
                    fullWidth
                    variant="contained"
                    color="success"
                    size="large"
                    onClick={() => handleHandoff(o.id)}
                    sx={{ py: 2 }}
                  >
                    Отдать "{o.name}"
                  </Button>
                ) : (
                  <ListItem
                    onClick={() => selectOrder(o.id)}
                    onDoubleClick={() => handleDoubleClick(o.id)}
                    sx={{
                      cursor: "pointer",
                      borderRadius: 1,
                      bgcolor: o.id === currentOrderId ? "action.selected" : "transparent",
                      flexDirection: "column",
                      alignItems: "stretch",
                      py: 1,
                    }}
                  >
                  <Box sx={{ display: "flex", alignItems: "center", width: "100%" }}>
                    <Box sx={{ flex: 1 }}>
                      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 0.5 }}>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {o.name}
                        </Typography>
                        <OrderTimer queuedAt={o.queuedAt} handoffAt={o.handoffAt} status={o.status} />
                      </Box>
                      <Typography variant="caption" color="text.secondary">
                        {new Date(o.createdAt).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })} • {money(orderTotal)} ₽
                        {o.isPaid && " • ✓ Оплачен"}
                      </Typography>
                    </Box>
                    <IconButton
                      size="small"
                      onClick={(e) => {
                        e.stopPropagation();
                        setViewOrder(o.id);
                      }}
                    >
                      <InfoIcon />
                    </IconButton>
                  </Box>

                  <Box sx={{ mt: 1, pl: 1, borderLeft: 2, borderColor: "divider" }}>
                    {o.comment && (
                      <Box sx={{ mb: 1, p: 1, bgcolor: "action.hover", borderRadius: 1 }}>
                        <Typography variant="caption" sx={{ fontWeight: 600, display: "block", mb: 0.5 }}>
                          💬 Комментарий:
                        </Typography>
                        <Typography variant="caption" sx={{ whiteSpace: "pre-wrap" }}>
                          {o.comment}
                        </Typography>
                      </Box>
                    )}

                    <Typography variant="caption" sx={{ fontWeight: 600, display: "block", mb: 0.5 }}>
                      🛒 Позиции ({orderLines.length}):
                    </Typography>
                    {orderLines.map((l) => (
                      <Box
                        key={l.lineId}
                        sx={{
                          display: "flex",
                          justifyContent: "space-between",
                          py: 0.5,
                          px: 1,
                          pl: l.isAddon ? 3 : 1,
                          "&:hover": { bgcolor: "action.hover" },
                          borderRadius: 0.5,
                        }}
                      >
                        <Typography variant="caption" color={l.isAddon ? "text.secondary" : "text.primary"}>
                          {l.isAddon ? `+ ${l.name}` : l.name} × {l.qty}
                        </Typography>
                        <Typography variant="caption" sx={{ fontWeight: 600 }} color={l.isAddon ? "text.secondary" : "text.primary"}>
                          {money(l.price * l.qty)} ₽
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                  </ListItem>
                )}
              </Box>
            );
          })}
          {filteredOrders.length === 0 && (
            <Typography sx={{ color: "text.secondary", p: 1 }}>
              Нет заказов
            </Typography>
          )}
      </List>
      </Paper>

      {/* Нижняя панель: Фильтры и кнопки */}
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
        <Paper variant="outlined" sx={{ p: 1 }}>
          <ToggleButtonGroup
            fullWidth
            exclusive
            value={statusFilter}
            onChange={(_, v) => v && setStatusFilter(v)}
          >
            <ToggleButton value="NEW">Очередь</ToggleButton>
            <ToggleButton value="HANDOFF">Отдали</ToggleButton>
          </ToggleButtonGroup>
        </Paper>

        <EndDayButton />
      </Box>

      <OrderCard
        order={viewOrder ? orders[viewOrder] : null}
        open={!!viewOrder}
        onClose={() => setViewOrder(null)}
      />
    </Box>
  );
}
