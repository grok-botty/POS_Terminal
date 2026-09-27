import { Box, Button, Paper, Typography } from "@mui/material";
import Grid from "@mui/material/Grid";
import { usePosStore } from "../../store";
import type { Product } from "../../types";

const products: Product[] = [
  { id: "latte", name: "Латте", price: 250, page: "drinks" },
  { id: "cap", name: "Капучино", price: 240, page: "drinks" },
  { id: "van", name: "Ваниль", price: 30, page: "syrups" },
  { id: "car", name: "Карамель", price: 30, page: "syrups" },
];

export function CatalogPage() {
  const page = usePosStore((s) => s.page);
  const addToCurrent = usePosStore((s) => s.addToCurrent);

  const list = products.filter((p) => p.page === page);

  return (
    <Box sx={{ p: 2 }}>
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>
          {page}
        </Typography>

        <Grid container spacing={1.2}>
          {list.map((p) => (
            <Grid key={p.id} size={{ xs: 6, sm: 4, md: 3, lg: 2 }}>
              <Button
                fullWidth
                variant="contained"
                onClick={() => addToCurrent(p)}
                sx={{ height: 72, textTransform: "none", fontWeight: 700 }}
              >
                {p.name}
              </Button>
            </Grid>
          ))}
        </Grid>
      </Paper>
    </Box>
  );
}
