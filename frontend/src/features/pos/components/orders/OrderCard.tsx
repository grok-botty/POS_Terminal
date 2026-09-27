import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  List,
  ListItem,
  ListItemText,
  Typography,
  Divider,
  Box,
} from "@mui/material";
import type { Order } from "../../types";

const money = (n: number) => new Intl.NumberFormat("ru-RU").format(n);

type Props = {
  order: Order | null;
  open: boolean;
  onClose: () => void;
};

export function OrderCard({ order, open, onClose }: Props) {
  if (!order) return null;

  const lines = Object.values(order.lines);
  const total = lines.reduce((sum, l) => sum + l.price * l.qty, 0);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ fontSize: "1.5rem", fontWeight: 700, pb: 1 }}>
        {order.name}
      </DialogTitle>
      <DialogContent>
        <Box sx={{ mb: 3 }}>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 0.5 }}>
            📅 Создан: {new Date(order.createdAt).toLocaleString("ru-RU")}
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 0.5 }}>
            📊 Статус: {order.status === "NEW" ? "Очередь" : "Выдано"}
          </Typography>
          <Typography variant="body1" color="text.secondary">
            💳 Оплата: {order.isPaid ? "Оплачен" : "Не оплачен"}
          </Typography>
        </Box>

        {order.comment && (
          <>
            <Box
              sx={{
                mb: 3,
                p: 2,
                bgcolor: "action.hover",
                borderRadius: 1,
                border: "1px solid",
                borderColor: "divider",
              }}
            >
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
                💬 Комментарий к заказу
              </Typography>
              <Typography variant="body1" sx={{ whiteSpace: "pre-wrap" }}>
                {order.comment}
              </Typography>
            </Box>
          </>
        )}

        <Divider sx={{ my: 2 }} />

        <Typography variant="h6" sx={{ mb: 2, fontWeight: 700 }}>
          🛒 Позиции заказа
        </Typography>

        {lines.length === 0 ? (
          <Typography variant="body1" color="text.secondary" sx={{ py: 2 }}>
            Заказ пуст
          </Typography>
        ) : (
          <List sx={{ bgcolor: "background.paper" }}>
            {lines.map((l, index) => (
              <Box key={l.productId}>
                <ListItem
                  sx={{
                    py: 2,
                    px: 2,
                    "&:hover": { bgcolor: "action.hover" },
                  }}
                >
                  <ListItemText
                    primary={
                      <Typography variant="body1" sx={{ fontWeight: 600, fontSize: "1.1rem" }}>
                        {l.name}
                      </Typography>
                    }
                    secondary={
                      <Box sx={{ mt: 0.5 }}>
                        <Typography variant="body1" component="span" color="text.secondary">
                          {money(l.price)} ₽ × {l.qty} шт. ={" "}
                        </Typography>
                        <Typography
                          variant="body1"
                          component="span"
                          sx={{ fontWeight: 600, color: "primary.main" }}
                        >
                          {money(l.price * l.qty)} ₽
                        </Typography>
                      </Box>
                    }
                  />
                </ListItem>
                {index < lines.length - 1 && <Divider />}
              </Box>
            ))}
          </List>
        )}

        <Divider sx={{ my: 3 }} />

        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            p: 2,
            bgcolor: "primary.main",
            color: "primary.contrastText",
            borderRadius: 1,
          }}
        >
          <Typography variant="h5" sx={{ fontWeight: 700 }}>
            Итого
          </Typography>
          <Typography variant="h4" sx={{ fontWeight: 800 }}>
            {money(total)} ₽
          </Typography>
        </Box>
      </DialogContent>
      <DialogActions sx={{ p: 2 }}>
        <Button onClick={onClose} variant="contained" size="large">
          Закрыть
        </Button>
      </DialogActions>
    </Dialog>
  );
}
