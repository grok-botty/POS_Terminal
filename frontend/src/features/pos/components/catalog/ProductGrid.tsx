import { Box, Button, Paper, Typography } from "@mui/material";
import Grid from "@mui/material/Grid";
import { usePosStore } from "../../store";

export function ProductGrid() {
  const products = usePosStore((s) => s.products);
  const categories = usePosStore((s) => s.categories);
  const page = usePosStore((s) => s.page);
  const addToCurrent = usePosStore((s) => s.addToCurrent);

  const currentCategory = categories.find((c) => c.slug === page);
  const filteredProducts = page === "all"
    ? products.filter((p) => p.is_active)
    : currentCategory
    ? products.filter((p) => p.category_id === currentCategory.id && p.is_active)
    : [];

  if (products.length === 0) {
    return (
      <Typography sx={{ color: "text.secondary", p: 2, textAlign: "center" }}>
        Нет продуктов. Добавьте их через "Редактировать меню"
      </Typography>
    );
  }

  if (filteredProducts.length === 0) {
    return (
      <Typography sx={{ color: "text.secondary", p: 2, textAlign: "center" }}>
        Нет продуктов в этой категории
      </Typography>
    );
  }

  // Если выбран раздел "Все", группируем по категориям
  if (page === "all") {
    const productsByCategory = categories.map((category) => ({
      category,
      products: filteredProducts.filter((p) => p.category_id === category.id),
    })).filter((group) => group.products.length > 0);

    return (
      <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
        {productsByCategory.map(({ category, products: categoryProducts }) => (
          <Paper key={category.id} variant="outlined" sx={{ p: 2 }}>
            <Typography variant="h6" sx={{ mb: 1.5, fontWeight: 600 }}>
              {category.name}
            </Typography>
            <Grid container spacing={1.2}>
              {categoryProducts.map((product) => (
                <Grid key={product.id} size={{ xs: 6, sm: 4, md: 3, lg: 2 }}>
                  <Button
                    fullWidth
                    variant="contained"
                    sx={{
                      minHeight: 72,
                      height: "auto",
                      py: 1.5,
                      textTransform: "none",
                      fontWeight: 700,
                      whiteSpace: "normal",
                      wordWrap: "break-word"
                    }}
                    onClick={() => addToCurrent(product)}
                  >
                    <Typography sx={{ fontSize: "0.9rem", fontWeight: 700 }}>
                      {product.name}
                    </Typography>
                  </Button>
                </Grid>
              ))}
            </Grid>
          </Paper>
        ))}
      </Box>
    );
  }

  // Обычное отображение для конкретной категории
  return (
    <Grid container spacing={1.2} sx={{ mt: 1 }}>
      {filteredProducts.map((product) => (
        <Grid key={product.id} size={{ xs: 6, sm: 4, md: 3, lg: 2 }}>
          <Button
            fullWidth
            variant="contained"
            sx={{
              minHeight: 72,
              height: "auto",
              py: 1.5,
              textTransform: "none",
              fontWeight: 700,
              whiteSpace: "normal",
              wordWrap: "break-word"
            }}
            onClick={() => addToCurrent(product)}
          >
            <Typography sx={{ fontSize: "0.9rem", fontWeight: 700 }}>
              {product.name}
            </Typography>
          </Button>
        </Grid>
      ))}
    </Grid>
  );
}
