import { useEffect, useState } from "react";
import { Box, IconButton, Tooltip, Button } from "@mui/material";
import LogoutIcon from "@mui/icons-material/Logout";
import ReceiptIcon from "@mui/icons-material/Receipt";
import SettingsIcon from "@mui/icons-material/Settings";
import {
  TopBar,
  CartPanel,
  CurrentOrderPanel,
  CatalogPanel,
  OrdersPage,
  AdminPage,
} from "./components";
import { usePosStore } from "./store";
import { useAuthStore } from "./authStore";

type Page = "pos" | "orders" | "admin";

export function PosScreen() {
  const [currentPage, setCurrentPage] = useState<Page>("pos");
  const loadCategories = usePosStore((s) => s.loadCategories);
  const loadProducts = usePosStore((s) => s.loadProducts);
  const logout = useAuthStore((s) => s.logout);
  const user = useAuthStore((s) => s.user);
  const isAdmin = useAuthStore((s) => s.isAdmin);

  useEffect(() => {
    loadCategories();
    loadProducts();
  }, [loadCategories, loadProducts]);

  if (currentPage === "orders") {
    return <OrdersPage onBack={() => setCurrentPage("pos")} />;
  }

  if (currentPage === "admin") {
    return <AdminPage onBack={() => setCurrentPage("pos")} />;
  }

  return (
    <Box
      sx={{
        height: "100vh",
        display: "grid",
        gridTemplateColumns: "360px 1fr 400px",
        bgcolor: "background.default",
        overflow: "hidden",
      }}
    >
      {/* Левая колонка: Список заказов */}
      <Box sx={{ borderRight: "1px solid", borderColor: "divider", overflow: "hidden" }}>
        <CartPanel />
      </Box>

      {/* Центральная колонка: Каталог */}
      <Box sx={{ display: "grid", gridTemplateRows: "64px 1fr", overflow: "hidden" }}>
        <Box sx={{ borderBottom: "1px solid", borderColor: "divider", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <TopBar />
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, px: 2 }}>
            {isAdmin() && (
              <>
                <Tooltip title="Администрирование">
                  <IconButton onClick={() => setCurrentPage("admin")} size="small">
                    <SettingsIcon />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Заказы по датам">
                  <Button
                    startIcon={<ReceiptIcon />}
                    onClick={() => setCurrentPage("orders")}
                    size="small"
                  >
                    Заказы
                  </Button>
                </Tooltip>
              </>
            )}
            <Tooltip title={`${user?.username} (${user?.role === 'admin' ? 'Администратор' : 'Пользователь'})`}>
              <span style={{ fontSize: "0.875rem", color: "#666" }}>{user?.username}</span>
            </Tooltip>
            <Tooltip title="Выйти">
              <IconButton onClick={logout} size="small">
                <LogoutIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        <Box sx={{ overflow: "auto" }}>
          <CatalogPanel />
        </Box>
      </Box>

      {/* Правая колонка: Текущий заказ */}
      <Box sx={{ borderLeft: "1px solid", borderColor: "divider", overflow: "hidden" }}>
        <CurrentOrderPanel />
      </Box>
    </Box>
  );
}
