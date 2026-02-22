export type OrderItem = {
  id: string;
  created_at: string;
  status: string;
  priority?: string | null;
  public_tracking_id: string;
  assigned_drone_id?: string | null;
};

export type OrdersListResponse = {
  items: OrderItem[];
  page: number;
  page_size: number;
  total: number;
};
