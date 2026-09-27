import { useEffect, useState } from "react";
import { Typography, Box } from "@mui/material";

type OrderTimerProps = {
  queuedAt?: number;
  handoffAt?: number;
  status: string;
};

export function OrderTimer({ queuedAt, handoffAt, status }: OrderTimerProps) {
  const [currentTime, setCurrentTime] = useState(() => Date.now());

  useEffect(() => {
    // Если заказ еще не в очереди, не показываем таймер
    if (!queuedAt) {
      return;
    }

    // Если заказ уже выдан, не обновляем время
    if (status === "HANDOFF") {
      return;
    }

    // Для активных заказов обновляем текущее время каждую секунду
    const interval = setInterval(() => {
      setCurrentTime(Date.now());
    }, 1000);

    return () => clearInterval(interval);
  }, [queuedAt, status]);

  // Если заказ еще не в очереди, не показываем таймер
  if (!queuedAt) {
    return null;
  }

  // Вычисляем elapsed время
  const elapsed = (() => {
    if (status === "HANDOFF" && handoffAt) {
      // Для отданных заказов показываем финальное время
      return Math.floor((handoffAt - queuedAt) / 1000);
    }
    // Для активных заказов показываем текущее время
    return Math.floor((currentTime - queuedAt) / 1000);
  })();

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // Определяем цвет в зависимости от времени
  const getColor = () => {
    if (status === "HANDOFF") return "text.secondary";
    if (elapsed < 180) return "success.main"; // < 3 минут - зеленый
    if (elapsed < 300) return "warning.main"; // < 5 минут - желтый
    return "error.main"; // >= 5 минут - красный
  };

  return (
    <Box sx={{ display: "inline-flex", alignItems: "center", gap: 0.5 }}>
      <Typography
        variant="caption"
        sx={{
          fontWeight: 600,
          color: getColor(),
          fontFamily: "monospace",
          fontSize: "0.85rem",
        }}
      >
        ⏱️ {formatTime(elapsed)}
      </Typography>
    </Box>
  );
}
