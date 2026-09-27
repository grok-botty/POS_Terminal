import type { Category, Product, DailyOrdersResponse, OrderDetail, AnalyticsResponse } from "./types";

const API_BASE = "/api";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function fetchWithAuth(url: string, options: RequestInit = {}) {
  const token = localStorage.getItem("auth-storage");
  let authToken = null;

  if (token) {
    try {
      const parsed = JSON.parse(token);
      authToken = parsed.state?.token;
    } catch (e) {
      console.error("Failed to parse auth token", e);
    }
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }

  if (options.headers) {
    Object.assign(headers, options.headers);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({ error: "Unknown error" }));
    throw new ApiError(response.status, data.error || `HTTP ${response.status}`);
  }

  return response.json();
}

export const api = {
  async getCategories(): Promise<{ categories: Category[] }> {
    return fetchWithAuth(`${API_BASE}/categories`);
  },

  async createCategory(name: string, slug: string, is_addon: boolean = false): Promise<Category> {
    return fetchWithAuth(`${API_BASE}/categories/create`, {
      method: "POST",
      body: JSON.stringify({ name, slug, is_addon }),
    });
  },

  async updateCategory(id: number, data: Partial<Category>): Promise<Category> {
    return fetchWithAuth(`${API_BASE}/categories/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  async reorderCategories(categories: { id: number; order: number }[]): Promise<void> {
    // Обновляем порядок каждой категории
    await Promise.all(
      categories.map(cat =>
        fetchWithAuth(`${API_BASE}/categories/${cat.id}`, {
          method: "PUT",
          body: JSON.stringify({ order: cat.order }),
        })
      )
    );
  },

  async deleteCategory(id: number): Promise<{ success: boolean }> {
    return fetchWithAuth(`${API_BASE}/categories/${id}/delete`, {
      method: "DELETE",
    });
  },

  async getProducts(categoryId?: number): Promise<{ products: Product[] }> {
    const url = categoryId
      ? `${API_BASE}/products?category_id=${categoryId}`
      : `${API_BASE}/products`;
    return fetchWithAuth(url);
  },

  async createProduct(data: {
    name: string;
    price: number;
    category_id: number;
  }): Promise<Product> {
    return fetchWithAuth(`${API_BASE}/products/create`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async updateProduct(id: number | string, data: Partial<Product>): Promise<Product> {
    return fetchWithAuth(`${API_BASE}/products/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  async deleteProduct(id: number | string): Promise<{ success: boolean }> {
    return fetchWithAuth(`${API_BASE}/products/${id}/delete`, {
      method: "DELETE",
    });
  },

  async getOrdersByDate(date: string): Promise<DailyOrdersResponse> {
    return fetchWithAuth(`${API_BASE}/orders?date=${date}`);
  },

  async updateOrder(
    id: number,
    data: Partial<OrderDetail>
  ): Promise<OrderDetail> {
    return fetchWithAuth(`${API_BASE}/orders/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  async deleteOrder(id: number): Promise<{ success: boolean }> {
    return fetchWithAuth(`${API_BASE}/orders/${id}/delete`, {
      method: "DELETE",
    });
  },

  async getAnalytics(days: number = 30): Promise<AnalyticsResponse> {
    return fetchWithAuth(`${API_BASE}/analytics?days=${days}`);
  },
};
