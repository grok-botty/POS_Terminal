import { useState } from "react";
import {
  Box,
  Paper,
  TextField,
  Button,
  Typography,
  Alert,
} from "@mui/material";

type Props = {
  onLogin: (token: string, user: { id: number; username: string; role: "admin" | "user" }) => void;
};

export function LoginScreen({ onLogin }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Ошибка авторизации");
      }

      onLogin(data.token, data.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Произошла ошибка");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box
      sx={{
        height: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        bgcolor: "background.default",
      }}
    >
      <Paper
        sx={{
          p: 4,
          width: "100%",
          maxWidth: 400,
        }}
      >
        <Typography variant="h4" sx={{ mb: 3, textAlign: "center" }}>
          Вход в систему
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <form onSubmit={handleSubmit}>
          <TextField
            fullWidth
            label="Имя пользователя"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            sx={{ mb: 2 }}
            autoFocus
            disabled={loading}
          />

          <TextField
            fullWidth
            label="Пароль"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            sx={{ mb: 3 }}
            disabled={loading}
          />

          <Button
            fullWidth
            variant="contained"
            type="submit"
            disabled={loading || !username || !password}
            sx={{ py: 1.5 }}
          >
            {loading ? "Вход..." : "Войти"}
          </Button>
        </form>

        <Box sx={{ mt: 3, p: 2, bgcolor: "action.hover", borderRadius: 1 }}>
          <Typography variant="caption" sx={{ display: "block" }}>
            Редактор: admin / admin
          </Typography>
          <Typography variant="caption" sx={{ display: "block" }}>
            Кассир: user / user
          </Typography>
          <Typography variant="caption" sx={{ display: "block", mt: 1 }}>
            Автор приложения:{" "}
            <a
              href="https://t.me/LotFullKa"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: "inherit", textDecoration: "underline" }}
            >
              @LotFullKa
            </a>
          </Typography>
        </Box>
      </Paper>
    </Box>
  );
}
