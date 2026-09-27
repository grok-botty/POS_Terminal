import { Box, Select, MenuItem, FormControl, InputLabel, Typography } from "@mui/material";
import { usePosStore } from "../../store";

export function TopBar() {
  const page = usePosStore((s) => s.page);
  const setPage = usePosStore((s) => s.setPage);
  const categories = usePosStore((s) => s.categories);

  return (
    <Box sx={{ height: 64, display: "flex", alignItems: "center", px: 2, gap: 2 }}>
      <Typography variant="h6" sx={{ fontWeight: 600 }}>
        Меню
      </Typography>

      <FormControl sx={{ minWidth: 200 }}>
        <InputLabel>Категория</InputLabel>
        <Select
          value={page}
          label="Категория"
          onChange={(e) => setPage(e.target.value)}
          size="small"
        >
          <MenuItem value="all">Все</MenuItem>
          {categories.map((c) => (
            <MenuItem key={c.id} value={c.slug}>
              {c.name}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </Box>
  );
}
