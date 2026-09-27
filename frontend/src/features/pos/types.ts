export type Page = string;

export type Category = {
  id: number;
  name: string;
  slug: string;
  order: number;
  is_addon?: boolean;
};

export type OrderStatus = "NEW" | "HANDOFF";

export type Product = {
  id: number | string;
  name: string;
  price: number;
  category_id?: number;
  is_active?: boolean;
  page?: string;
};

export type CartLine = {
  lineId: string;
  productId: string;
  name: string;
  price: number;
  qty: number;
  categoryId?: number;
  isAddon?: boolean;
};

export type Order = {
  id: string;
  name: string;
  comment: string;
  status: OrderStatus;
  createdAt: number;
  queuedAt?: number; // Время когда заказ попал в очередь
  handoffAt?: number; // Время когда заказ был отдан
  lines: Record<string, CartLine>;
  isPaid: boolean;
  lineOrder: string[];
};

export type OrderLine = {
  product_id: string;
  name: string;
  price: number;
  qty: number;
};

export type OrderDetail = {
  id: number;
  order_id: string;
  name: string;
  comment: string;
  status: string;
  total: number;
  is_paid: boolean;
  created_at: string;
  lines: OrderLine[];
};

export type DailyOrdersResponse = {
  date: string;
  total_revenue: number;
  total_orders: number;
  orders: OrderDetail[];
};

export type RevenueByDay = {
  date: string;
  revenue: number;
  orders: number;
};

export type TopProduct = {
  product_id: string;
  name: string;
  quantity: number;
  revenue: number;
};

export type HourlyStat = {
  hour: number;
  orders: number;
  revenue: number;
};

export type WeekdayStat = {
  weekday: string;
  orders: number;
  revenue: number;
  avg_check: number;
};

export type QueueStats = {
  avg_time: number;
  min_time: number;
  max_time: number;
  total_orders_with_time: number;
};

export type AnalyticsResponse = {
  period: {
    start_date: string;
    end_date: string;
    days: number;
  };
  summary: {
    total_revenue: number;
    total_orders: number;
    avg_order_value: number;
    paid_orders: number;
    unpaid_orders: number;
    paid_revenue: number;
  };
  revenue_by_day: RevenueByDay[];
  top_products: TopProduct[];
  hourly_stats: HourlyStat[];
  weekday_stats: WeekdayStat[];
  queue_stats: QueueStats;
};
