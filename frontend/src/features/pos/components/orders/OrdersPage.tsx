import { useState, useEffect } from "react";
import {
  Box,
  Typography,
  Paper,
  TextField,
  Button,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Alert,
  Tabs,
  Tab,
} from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import { api } from "../../api";
import type { OrderDetail } from "../../types";
import { AnalyticsTab } from "./AnalyticsTab";

type OrdersPageProps = {
  onBack: () => void;
};

export function OrdersPage({ onBack }: OrdersPageProps) {
  const [activeTab, setActiveTab] = useState(0);
  const [date, setDate] = useState(() => {
    const today = new Date();
    return today.toISOString().split("T")[0];
  });
  const [orders, setOrders] = useState<OrderDetail[]>([]);
  const [totalRevenue, setTotalRevenue] = useState(0);
  const [totalOrders, setTotalOrders] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingOrder, setEditingOrder] = useState<OrderDetail | null>(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);

  const loadOrders = async (selectedDate: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.getOrdersByDate(selectedDate);
      setOrders(response.orders);
      setTotalRevenue(response.total_revenue);
      setTotalOrders(response.total_orders);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки заказов");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOrders(date);
  }, [date]);

  const handleEdit = (order: OrderDetail) => {
    setEditingOrder({ ...order });
    setEditDialogOpen(true);
  };

  const handleSaveEdit = async () => {
    if (!editingOrder) return;

    try {
      await api.updateOrder(editingOrder.id, {
        name: editingOrder.name,
        comment: editingOrder.comment,
        status: editingOrder.status,
        is_paid: editingOrder.is_paid,
      });
      setEditDialogOpen(false);
      setEditingOrder(null);
      loadOrders(date);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка обновления заказа");
    }
  };

  const handleDelete = async (orderId: number) => {
    if (!confirm("Вы уверены, что хотите удалить этот заказ?")) return;

    try {
      await api.deleteOrder(orderId);
      loadOrders(date);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка удаления заказа");
    }
  };

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 3 }}>
        <IconButton onClick={onBack}>
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h4">Заказы и аналитика</Typography>
      </Box>

      <Box sx={{ borderBottom: 1, borderColor: "divider", mb: 3 }}>
        <Tabs value={activeTab} onChange={(_, newValue) => setActiveTab(newValue)}>
          <Tab label="Заказы за дату" />
          <Tab label="Аналитика" />
        </Tabs>
      </Box>

      {activeTab === 0 && (
        <>
          <Box sx={{ display: "flex", gap: 2, mb: 3, alignItems: "center" }}>
            <TextField
              type="date"
              label="Дата"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              InputLabelProps={{ shrink: true }}
            />
            <Button variant="contained" onClick={() => loadOrders(date)}>
              Загрузить
            </Button>
          </Box>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          <Paper sx={{ p: 2, mb: 3 }}>
            <Typography variant="h6">Сводка за {date}</Typography>
            <Typography>Всего заказов: {totalOrders}</Typography>
            <Typography>Общая выручка: {totalRevenue.toFixed(2)} ₽</Typography>
          </Paper>

          {loading ? (
            <Typography>Загрузка...</Typography>
          ) : orders.length === 0 ? (
            <Typography>Нет заказов за выбранную дату</Typography>
          ) : (
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>ID</TableCell>
                    <TableCell>Имя</TableCell>
                    <TableCell>Дата/Время</TableCell>
                    <TableCell>Статус</TableCell>
                    <TableCell>Сумма</TableCell>
                    <TableCell>Оплачен</TableCell>
                    <TableCell>Комментарий</TableCell>
                    <TableCell>Действия</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {orders.map((order) => (
                    <TableRow key={order.id}>
                      <TableCell>{order.order_id}</TableCell>
                      <TableCell>{order.name}</TableCell>
                      <TableCell>{formatDate(order.created_at)}</TableCell>
                      <TableCell>
                        <Chip
                          label={order.status}
                          color={order.status === "NEW" ? "primary" : "default"}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>{order.total.toFixed(2)} ₽</TableCell>
                      <TableCell>
                        <Chip
                          label={order.is_paid ? "Да" : "Нет"}
                          color={order.is_paid ? "success" : "default"}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>{order.comment || "-"}</TableCell>
                      <TableCell>
                        <IconButton
                          size="small"
                          onClick={() => handleEdit(order)}
                          color="primary"
                        >
                          <EditIcon />
                        </IconButton>
                        <IconButton
                          size="small"
                          onClick={() => handleDelete(order.id)}
                          color="error"
                        >
                          <DeleteIcon />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </>
      )}

      {activeTab === 1 && <AnalyticsTab />}

      {/* Диалог редактирования */}
      <Dialog
        open={editDialogOpen}
        onClose={() => setEditDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Редактировать заказ</DialogTitle>
        <DialogContent>
          {editingOrder && (
            <Box sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 2 }}>
              <TextField
                label="Имя клиента"
                value={editingOrder.name}
                onChange={(e) =>
                  setEditingOrder({ ...editingOrder, name: e.target.value })
                }
                fullWidth
              />
              <TextField
                label="Комментарий"
                value={editingOrder.comment || ""}
                onChange={(e) =>
                  setEditingOrder({ ...editingOrder, comment: e.target.value })
                }
                fullWidth
                multiline
                rows={3}
              />
              <TextField
                label="Статус"
                value={editingOrder.status}
                onChange={(e) =>
                  setEditingOrder({ ...editingOrder, status: e.target.value })
                }
                fullWidth
                select
                SelectProps={{ native: true }}
              >
                <option value="NEW">NEW</option>
                <option value="HANDOFF">HANDOFF</option>
              </TextField>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <input
                  type="checkbox"
                  checked={editingOrder.is_paid}
                  onChange={(e) =>
                    setEditingOrder({ ...editingOrder, is_paid: e.target.checked })
                  }
                  id="is-paid-checkbox"
                />
                <label htmlFor="is-paid-checkbox">Оплачен</label>
              </Box>

              <Typography variant="h6" sx={{ mt: 2 }}>
                Позиции заказа
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Товар</TableCell>
                      <TableCell>Цена</TableCell>
                      <TableCell>Кол-во</TableCell>
                      <TableCell>Сумма</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {editingOrder.lines.map((line, idx) => (
                      <TableRow key={idx}>
                        <TableCell>{line.name}</TableCell>
                        <TableCell>{line.price.toFixed(2)} ₽</TableCell>
                        <TableCell>{line.qty}</TableCell>
                        <TableCell>{(line.price * line.qty).toFixed(2)} ₽</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
              <Typography variant="h6">
                Итого: {editingOrder.total.toFixed(2)} ₽
              </Typography>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialogOpen(false)}>Отмена</Button>
          <Button onClick={handleSaveEdit} variant="contained">
            Сохранить
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
