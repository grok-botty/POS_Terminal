import { useState, useEffect } from "react";
import {
  Box,
  Typography,
  Paper,
  Card,
  CardContent,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  CircularProgress,
} from "@mui/material";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { api } from "../../api";
import type { AnalyticsResponse } from "../../types";

const COLORS = [
  "#0088FE",
  "#00C49F",
  "#FFBB28",
  "#FF8042",
  "#8884D8",
  "#82CA9D",
  "#FFC658",
  "#FF6B9D",
  "#C084FC",
  "#34D399",
];

export function AnalyticsTab() {
  const [period, setPeriod] = useState(30);
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAnalytics = async (days: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getAnalytics(days);
      setAnalytics(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки аналитики");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAnalytics(period);
  }, [period]);

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ m: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!analytics) {
    return null;
  }

  const { summary, revenue_by_day, top_products, hourly_stats, weekday_stats, queue_stats } =
    analytics;

  // Форматирование времени из секунд в минуты:секунды
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", mb: 3 }}>
        <Typography variant="h5">Аналитика</Typography>
        <FormControl sx={{ minWidth: 200 }}>
          <InputLabel>Период</InputLabel>
          <Select
            value={period}
            label="Период"
            onChange={(e) => setPeriod(Number(e.target.value))}
          >
            <MenuItem value={7}>Последние 7 дней</MenuItem>
            <MenuItem value={14}>Последние 14 дней</MenuItem>
            <MenuItem value={30}>Последние 30 дней</MenuItem>
            <MenuItem value={90}>Последние 90 дней</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {/* Общая статистика */}
      <Box sx={{ display: "flex", gap: 2, mb: 4, flexWrap: "wrap" }}>
        <Card sx={{ flex: "1 1 200px" }}>
          <CardContent>
            <Typography color="textSecondary" gutterBottom>
              Общая выручка
            </Typography>
            <Typography variant="h5">
              {summary.total_revenue.toFixed(2)} ₽
            </Typography>
          </CardContent>
        </Card>
        <Card sx={{ flex: "1 1 200px" }}>
          <CardContent>
            <Typography color="textSecondary" gutterBottom>
              Всего заказов
            </Typography>
            <Typography variant="h5">{summary.total_orders}</Typography>
          </CardContent>
        </Card>
        <Card sx={{ flex: "1 1 200px" }}>
          <CardContent>
            <Typography color="textSecondary" gutterBottom>
              Средний чек
            </Typography>
            <Typography variant="h5">
              {summary.avg_order_value.toFixed(2)} ₽
            </Typography>
          </CardContent>
        </Card>
        <Card sx={{ flex: "1 1 200px" }}>
          <CardContent>
            <Typography color="textSecondary" gutterBottom>
              Оплачено / Не оплачено
            </Typography>
            <Typography variant="h5">
              {summary.paid_orders} / {summary.unpaid_orders}
            </Typography>
          </CardContent>
        </Card>
        {queue_stats.total_orders_with_time > 0 && (
          <Card sx={{ flex: "1 1 200px" }}>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                ⏱️ Среднее время в очереди
              </Typography>
              <Typography variant="h5">
                {formatTime(queue_stats.avg_time)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Мин: {formatTime(queue_stats.min_time)} | Макс: {formatTime(queue_stats.max_time)}
              </Typography>
            </CardContent>
          </Card>
        )}
      </Box>

      {/* График выручки по дням */}
      <Paper sx={{ p: 3, mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          Выручка по дням
        </Typography>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={revenue_by_day}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line
              type="monotone"
              dataKey="revenue"
              stroke="#8884d8"
              name="Выручка (₽)"
              strokeWidth={2}
            />
            <Line
              type="monotone"
              dataKey="orders"
              stroke="#82ca9d"
              name="Заказов"
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
      </Paper>

      {/* Топ продуктов */}
      <Paper sx={{ p: 3, mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          Топ-10 продуктов по выручке
        </Typography>
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={top_products} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" />
            <YAxis dataKey="name" type="category" width={150} />
            <Tooltip />
            <Legend />
            <Bar dataKey="revenue" fill="#8884d8" name="Выручка (₽)">
              {top_products.map((_, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Paper>

      <Box sx={{ display: "flex", gap: 3, flexWrap: "wrap", mb: 4 }}>
        {/* Статистика по часам */}
        <Paper sx={{ p: 3, flex: "1 1 400px" }}>
          <Typography variant="h6" gutterBottom>
            Заказы по часам
          </Typography>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={hourly_stats}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="hour" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="orders" fill="#8884d8" name="Заказов" />
              <Bar dataKey="revenue" fill="#82ca9d" name="Выручка (₽)" />
            </BarChart>
          </ResponsiveContainer>
        </Paper>

        {/* Статистика по дням недели */}
        <Paper sx={{ p: 3, flex: "1 1 400px" }}>
          <Typography variant="h6" gutterBottom>
            Средний чек по дням недели
          </Typography>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={weekday_stats}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="weekday" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="avg_check" fill="#FF8042" name="Средний чек (₽)" />
            </BarChart>
          </ResponsiveContainer>
        </Paper>

        {/* Круговая диаграмма топ-5 продуктов */}
        <Paper sx={{ p: 3, flex: "1 1 400px" }}>
          <Typography variant="h6" gutterBottom>
            Топ-5 продуктов (по количеству)
          </Typography>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={top_products.slice(0, 5)}
                dataKey="quantity"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label
              >
                {top_products.slice(0, 5).map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Paper>

        {/* Статистика оплаты */}
        <Paper sx={{ p: 3, flex: "1 1 400px" }}>
          <Typography variant="h6" gutterBottom>
            Статус оплаты
          </Typography>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={[
                  { name: "Оплачено", value: summary.paid_orders },
                  { name: "Не оплачено", value: summary.unpaid_orders },
                ]}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label
              >
                <Cell fill="#00C49F" />
                <Cell fill="#FF8042" />
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
          <Box sx={{ mt: 2 }}>
            <Typography variant="body2" color="textSecondary">
              Выручка от оплаченных: {summary.paid_revenue.toFixed(2)} ₽
            </Typography>
            <Typography variant="body2" color="textSecondary">
              Процент оплаченных:{" "}
              {summary.total_orders > 0
                ? ((summary.paid_orders / summary.total_orders) * 100).toFixed(1)
                : 0}
              %
            </Typography>
          </Box>
        </Paper>

        {/* Статистика по времени обработки */}
        {queue_stats.total_orders_with_time > 0 && (
          <Paper sx={{ p: 3, flex: "1 1 400px" }}>
            <Typography variant="h6" gutterBottom>
              Время обработки заказов
            </Typography>
            <Box sx={{ mt: 2 }}>
              <Typography variant="body1" sx={{ mb: 1 }}>
                📊 Всего заказов с данными: {queue_stats.total_orders_with_time}
              </Typography>
              <Typography variant="body1" sx={{ mb: 1 }}>
                ⏱️ Среднее время: {formatTime(queue_stats.avg_time)}
              </Typography>
              <Typography variant="body1" sx={{ mb: 1 }}>
                🟢 Минимальное: {formatTime(queue_stats.min_time)}
              </Typography>
              <Typography variant="body1">
                🔴 Максимальное: {formatTime(queue_stats.max_time)}
              </Typography>
            </Box>
          </Paper>
        )}
      </Box>
    </Box>
  );
}
