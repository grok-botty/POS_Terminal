import { create } from "zustand";
import type { Order, OrderStatus, Page, Product, Category } from "./types";
import { api } from "./api";
import { generateFunnyOrderName } from "./orderNameGenerator";

const uid = () => Math.random().toString(36).slice(2, 9);

type State = {
  page: Page;
  setPage: (p: Page) => void;

  statusFilter: OrderStatus;
  setStatusFilter: (s: OrderStatus) => void;

  orders: Record<string, Order>;
  currentOrderId: string | null;

  ensureCurrent: () => string;
  newOrder: () => string;
  selectOrder: (id: string) => void;
  setOrderStatus: (id: string, status: OrderStatus) => void;
  setOrderName: (id: string, name: string) => void;
  setOrderComment: (id: string, comment: string) => void;
  toggleOrderPaid: (id: string) => void;
  moveToQueueAndCreateNew: () => string;

  addToCurrent: (p: Product) => void;
  incLine: (lineId: string) => void;
  decLine: (lineId: string) => void;
  clearCurrent: () => void;
  cancelOrder: (id: string) => void;
  reorderLines: (orderId: string, productIds: string[]) => void;

  products: Product[];
  categories: Category[];

  loadCategories: () => Promise<void>;
  loadProducts: (categoryId?: number) => Promise<void>;

  addProduct: (product: Omit<Product, "id" | "is_active">) => Promise<void>;
  updateProduct: (id: number | string, product: Partial<Omit<Product, "id">>) => Promise<void>;
  deleteProduct: (id: number | string) => Promise<void>;

  addCategory: (name: string, slug: string, is_addon?: boolean) => Promise<void>;
  updateCategory: (id: number, name: string, is_addon?: boolean) => Promise<void>;
  deleteCategory: (id: number) => Promise<void>;
  reorderCategories: (categoryIds: number[]) => Promise<void>;
};

export const usePosStore = create<State>()((set, get) => ({
  page: "drinks",
  setPage: (p) => set({ page: p }),

  statusFilter: "NEW",
  setStatusFilter: (s) => set({ statusFilter: s }),

  orders: {},
  currentOrderId: null,

  ensureCurrent: () => {
    const s = get();
    if (s.currentOrderId && s.orders[s.currentOrderId]) return s.currentOrderId;
    return get().newOrder();
  },

  newOrder: () => {
    const id = uid();
    const order: Order = {
      id,
      name: generateFunnyOrderName(),
      comment: "",
      status: "NEW",
      createdAt: Date.now(),
      queuedAt: undefined, // Еще не в очереди
      lines: {},
      isPaid: false,
      lineOrder: [],
    };
    set((s) => ({ orders: { ...s.orders, [id]: order }, currentOrderId: id }));
    return id;
  },

  selectOrder: (id) => set({ currentOrderId: id }),

  setOrderStatus: (id, status) =>
    set((s) => {
      const order = s.orders[id];
      if (!order) return s;

      // Если меняем статус на HANDOFF, сохраняем время отдачи
      const updates: Partial<Order> = { status };
      if (status === "HANDOFF" && !order.handoffAt) {
        updates.handoffAt = Date.now();
      }

      return {
        orders: { ...s.orders, [id]: { ...order, ...updates } },
      };
    }),

  setOrderName: (id, name) =>
    set((s) => ({
      orders: { ...s.orders, [id]: { ...s.orders[id], name } },
    })),

  setOrderComment: (id, comment) =>
    set((s) => ({
      orders: { ...s.orders, [id]: { ...s.orders[id], comment } },
    })),

  addToCurrent: (p) =>
    set((s) => {
      const orderId = s.currentOrderId ?? uid();
      const order =
        s.orders[orderId] ??
        ({
          id: orderId,
          name: generateFunnyOrderName(),
          comment: "",
          status: "NEW",
          createdAt: Date.now(),
          queuedAt: undefined,
          lines: {},
          isPaid: false,
          lineOrder: [],
        } as Order);

      // Проверяем, является ли категория товара добавкой
      const category = s.categories.find(c => c.id === p.category_id);
      const isAddon = category?.is_addon || false;

      // Всегда создаем новую строку с уникальным lineId
      const lineId = uid();
      const lines = {
        ...order.lines,
        [lineId]: {
          lineId,
          productId: String(p.id),
          name: p.name,
          price: p.price,
          qty: 1,
          categoryId: p.category_id,
          isAddon
        },
      };

      // Добавляем новую строку в конец
      const lineOrder = [...order.lineOrder, lineId];

      return {
        currentOrderId: orderId,
        orders: { ...s.orders, [orderId]: { ...order, lines, lineOrder } },
      };
    }),

  incLine: (lineId) =>
    set((s) => {
      if (!s.currentOrderId) return s;
      const o = s.orders[s.currentOrderId];
      const line = o?.lines[lineId];
      if (!o || !line) return s;
      return {
        orders: {
          ...s.orders,
          [o.id]: {
            ...o,
            lines: { ...o.lines, [lineId]: { ...line, qty: line.qty + 1 } },
          },
        },
      };
    }),

  decLine: (lineId) =>
    set((s) => {
      if (!s.currentOrderId) return s;
      const o = s.orders[s.currentOrderId];
      const line = o?.lines[lineId];
      if (!o || !line) return s;

      const lines = { ...o.lines };
      let lineOrder = o.lineOrder;

      if (line.qty <= 1) {
        delete lines[lineId];
        lineOrder = lineOrder.filter(id => id !== lineId);
      } else {
        lines[lineId] = { ...line, qty: line.qty - 1 };
      }

      return { orders: { ...s.orders, [o.id]: { ...o, lines, lineOrder } } };
    }),

  clearCurrent: () =>
    set((s) => {
      if (!s.currentOrderId) return s;
      const o = s.orders[s.currentOrderId];
      if (!o) return s;
      return { orders: { ...s.orders, [o.id]: { ...o, lines: {} } } };
    }),

  toggleOrderPaid: (id) =>
    set((s) => ({
      orders: {
        ...s.orders,
        [id]: { ...s.orders[id], isPaid: !s.orders[id].isPaid },
      },
    })),

  moveToQueueAndCreateNew: () => {
    const s = get();
    if (s.currentOrderId && s.orders[s.currentOrderId]) {
      // Устанавливаем время попадания в очередь
      set((state) => ({
        orders: {
          ...state.orders,
          [s.currentOrderId!]: {
            ...state.orders[s.currentOrderId!],
            queuedAt: Date.now(),
          },
        },
      }));
    }
    // Создаем новый заказ
    return get().newOrder();
  },

  cancelOrder: (id) =>
    set((s) => {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { [id]: _, ...remainingOrders } = s.orders;
      return {
        orders: remainingOrders,
        currentOrderId: s.currentOrderId === id ? null : s.currentOrderId,
      };
    }),

  reorderLines: (orderId, lineIds) =>
    set((s) => {
      const order = s.orders[orderId];
      if (!order) return s;

      return {
        orders: {
          ...s.orders,
          [orderId]: { ...order, lineOrder: lineIds }
        }
      };
    }),

  products: [],
  categories: [],

  loadCategories: async () => {
    try {
      const { categories } = await api.getCategories();
      set({ categories });
      if (categories.length > 0 && !get().page) {
        set({ page: categories[0].slug });
      }
    } catch (error) {
      console.error("Failed to load categories:", error);
    }
  },

  loadProducts: async (categoryId?: number) => {
    try {
      const { products } = await api.getProducts(categoryId);
      set({ products });
    } catch (error) {
      console.error("Failed to load products:", error);
    }
  },

  addProduct: async (product) => {
    try {
      const newProduct = await api.createProduct({
        name: product.name,
        price: product.price,
        category_id: product.category_id ?? 0,
      });
      set((s) => ({ products: [...s.products, newProduct] }));
    } catch (error) {
      console.error("Failed to add product:", error);
      throw error;
    }
  },

  updateProduct: async (id, updates) => {
    try {
      const updated = await api.updateProduct(id, updates);
      set((s) => ({
        products: s.products.map((p) => (p.id === id ? updated : p)),
      }));
    } catch (error) {
      console.error("Failed to update product:", error);
      throw error;
    }
  },

  deleteProduct: async (id) => {
    try {
      await api.deleteProduct(id);
      set((s) => ({
        products: s.products.filter((p) => p.id !== id),
      }));
    } catch (error) {
      console.error("Failed to delete product:", error);
      throw error;
    }
  },

  addCategory: async (name, slug, is_addon = false) => {
    try {
      const newCategory = await api.createCategory(name, slug, is_addon);
      set((s) => ({
        categories: [...s.categories, newCategory],
        page: newCategory.slug,
      }));
    } catch (error) {
      console.error("Failed to add category:", error);
      throw error;
    }
  },

  updateCategory: async (id, name, is_addon) => {
    try {
      const updates: Partial<Category> = { name };
      if (is_addon !== undefined) {
        updates.is_addon = is_addon;
      }
      const updated = await api.updateCategory(id, updates);
      set((s) => ({
        categories: s.categories.map((c) => (c.id === id ? updated : c)),
      }));
    } catch (error) {
      console.error("Failed to update category:", error);
      throw error;
    }
  },

  deleteCategory: async (id) => {
    try {
      await api.deleteCategory(id);
      set((s) => {
        const newCategories = s.categories.filter((c) => c.id !== id);
        return {
          categories: newCategories,
          products: s.products.filter((p) => p.category_id !== id),
          page:
            s.page === String(id)
              ? newCategories[0]?.slug ?? "drinks"
              : s.page,
        };
      });
    } catch (error) {
      console.error("Failed to delete category:", error);
      throw error;
    }
  },

  reorderCategories: async (categoryIds) => {
    try {
      const updates = categoryIds.map((id, index) => ({
        id,
        order: index,
      }));

      await api.reorderCategories(updates);

      set((s) => {
        const categoriesMap = new Map(s.categories.map(c => [c.id, c]));
        const reordered = categoryIds
          .map(id => categoriesMap.get(id))
          .filter((c): c is Category => c !== undefined)
          .map((c, index) => ({ ...c, order: index }));

        return { categories: reordered };
      });
    } catch (error) {
      console.error("Failed to reorder categories:", error);
      throw error;
    }
  },
}));
