import { useState } from "react";
import {
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Typography,
  Box,
  CircularProgress,
  Alert,
} from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import { usePosStore } from "../../store";

const money = (n: number) => new Intl.NumberFormat("ru-RU").format(n);

export function EndDayButton() {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    success: boolean;
    message: string;
    data?: {
      date: string;
      total_revenue: number;
      total_orders: number;
      paid_orders: number;
      unpaid_orders: number;
      saved_to_db: boolean;
      saved_to_sheets: boolean;
    };
  } | null>(null);

  const orders = usePosStore((s) => s.orders);

  const handleOpen = () => {
    setOpen(true);
    setResult(null);
  };

  const handleClose = () => {
    setOpen(false);
    setResult(null);
  };

  const handleEndDay = async () => {
    setLoading(true);
    setResult(null);

    try {
      const ordersArray = Object.values(orders);

      const response = await fetch("/api/end-day", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          orders: ordersArray,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Ошибка при закрытии дня");
      }

      setResult({
        success: true,
        message: data.message,
        data,
      });
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : "Произошла ошибка";
      setResult({
        success: false,
        message: errorMessage,
      });
    } finally {
      setLoading(false);
    }
  };

  const totalOrders = Object.keys(orders).length;
  const paidOrders = Object.values(orders).filter((o) => o.isPaid).length;
  const unpaidOrders = totalOrders - paidOrders;
  const totalRevenue = Object.values(orders).reduce((sum, order) => {
    const orderTotal = Object.values(order.lines).reduce(
      (lineSum, line) => lineSum + line.price * line.qty,
      0
    );
    return sum + orderTotal;
  }, 0);

  return (
    <>
      <Button
        variant="contained"
        color="success"
        onClick={handleOpen}
        disabled={totalOrders === 0}
        sx={{ fontWeight: 700 }}
      >
        Закончить день
      </Button>

      <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
        <DialogTitle>
          {result?.success ? "День закрыт!" : "Закрытие дня"}
        </DialogTitle>
        <DialogContent>
          {!result && !loading && (
            <Box>
              <Typography variant="body1" sx={{ mb: 2 }}>
                Вы уверены, что хотите закончить день?
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                Это действие сохранит все заказы в базу данных и отправит отчёт
                в Google Таблицу.
              </Typography>

              <Box
                sx={{
                  mt: 3,
                  p: 2,
                  bgcolor: "background.paper",
                  borderRadius: 1,
                  border: "1px solid",
                  borderColor: "divider",
                }}
              >
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Сводка за день:
                </Typography>
                <Box sx={{ display: "flex", flexDirection: "column", gap: 0.5 }}>
                  <Typography variant="body2">
                    Всего заказов: <strong>{totalOrders}</strong>
                  </Typography>
                  <Typography variant="body2">
                    Оплачено: <strong>{paidOrders}</strong>
                  </Typography>
                  <Typography variant="body2">
                    Не оплачено: <strong>{unpaidOrders}</strong>
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 1, fontSize: "1.1rem" }}>
                    Выручка: <strong>{money(totalRevenue)} ₽</strong>
                  </Typography>
                </Box>
              </Box>
            </Box>
          )}

          {loading && (
            <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", py: 3 }}>
              <CircularProgress />
              <Typography sx={{ mt: 2 }}>Сохранение данных...</Typography>
            </Box>
          )}

          {result && (
            <Box>
              <Alert severity={result.success ? "success" : "error"} sx={{ mb: 2 }}>
                {result.message}
              </Alert>

              {result.success && result.data && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    <CheckCircleIcon
                      sx={{ fontSize: 16, verticalAlign: "middle", mr: 0.5 }}
                    />
                    Сохранено в БД: {result.data.saved_to_db ? "Да" : "Нет"}
                  </Typography>
                  <Typography variant="body2">
                    <CheckCircleIcon
                      sx={{ fontSize: 16, verticalAlign: "middle", mr: 0.5 }}
                    />
                    Отправлено в Google Sheets:{" "}
                    {result.data.saved_to_sheets ? "Да" : "Нет"}
                  </Typography>

                  <Box
                    sx={{
                      mt: 2,
                      p: 2,
                      bgcolor: "success.light",
                      borderRadius: 1,
                    }}
                  >
                    <Typography variant="body2">
                      Дата: <strong>{result.data.date}</strong>
                    </Typography>
                    <Typography variant="body2">
                      Выручка: <strong>{money(result.data.total_revenue)} ₽</strong>
                    </Typography>
                    <Typography variant="body2">
                      Заказов: <strong>{result.data.total_orders}</strong>
                    </Typography>
                  </Box>
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          {!result && (
            <>
              <Button onClick={handleClose} disabled={loading}>
                Отмена
              </Button>
              <Button
                onClick={handleEndDay}
                variant="contained"
                color="success"
                disabled={loading}
              >
                Подтвердить
              </Button>
            </>
          )}
          {result && (
            <Button onClick={handleClose} variant="contained">
              Закрыть
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </>
  );
}
