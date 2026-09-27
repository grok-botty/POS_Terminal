import { Box, Button, Typography, Tabs, Tab } from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import { useState } from "react";
import { useAuthStore } from "../../authStore";
import { ProductManager } from "./ProductManager";
import { CategoryManager } from "./CategoryManager";

type AdminPageProps = {
  onBack: () => void;
};

export function AdminPage({ onBack }: AdminPageProps) {
  const [tab, setTab] = useState(0);
  const isAdmin = useAuthStore((s) => s.isAdmin());

  if (!isAdmin) {
    return null;
  }

  return (
    <Box sx={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      <Box
        sx={{
          borderBottom: "1px solid",
          borderColor: "divider",
          p: 2,
          display: "flex",
          alignItems: "center",
          gap: 2,
        }}
      >
        <Button startIcon={<ArrowBackIcon />} onClick={onBack} variant="outlined">
          Назад
        </Button>
        <Typography variant="h5" sx={{ fontWeight: 600 }}>
          Администрирование
        </Typography>
      </Box>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Tab label="Продукты" />
        <Tab label="Категории" />
      </Tabs>

      <Box sx={{ flex: 1, overflow: "auto", p: 3 }}>
        {tab === 0 && <ProductManager />}
        {tab === 1 && <CategoryManager />}
      </Box>
    </Box>
  );
}
