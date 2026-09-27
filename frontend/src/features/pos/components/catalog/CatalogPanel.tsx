import { Box } from "@mui/material";
import { ProductGrid } from "./ProductGrid";

export function CatalogPanel() {
  return (
    <Box sx={{ p: 2 }}>
      <ProductGrid />
    </Box>
  );
}
