export interface HealthResponse {
  ok: boolean;
  app: string;
  environment: string;
}

export interface DatabaseHealthResponse {
  ok: boolean;
  database: string;
  user: string;
  host: string;
}

export interface FacturaDisponible {
  factura: string;
  nit: string;
  lineas_xml: number;
}

export interface DashboardMetric {
  xml: number;
  erp: number;
  diferencia: number;
  ajuste_ac: number;
  ajuste_np: number;
  ajuste_sugerido: number;
  saldo: number;
}

export interface DashboardPayload {
  titulo: string;
  requiere_validacion: boolean;
  total_items: number;
  items_con_diferencia: number;
  alertas_rescate: number;
  conteos_estado: Record<string, number>;
  costo: DashboardMetric;
  unidades: DashboardMetric;
}

export interface TableSummaryItem {
  label: string;
  value: number;
}

export interface TablePayload {
  columns: string[];
  rows: Array<Record<string, unknown>>;
  totals: Record<string, unknown>;
  summary: TableSummaryItem[];
}

export interface ConciliacionResponse {
  factura: string;
  nit: string;
  dashboard: DashboardPayload;
  detalle: TablePayload;
  ac: TablePayload;
  np: TablePayload;
}

export interface ProcessedInvoice {
  factura: string;
  nit: string;
  lineas_xml: number;
  origen: string;
}

export interface ProcessedBatchResponse {
  procesadas: ProcessedInvoice[];
  total_procesadas: number;
}

export interface AuthUser {
  id: number;
  username: string;
  full_name: string;
  is_admin: boolean;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface LoginResponse {
  token: string;
  expires_at: string;
  user: AuthUser;
}

export interface UserSummary {
  id: number;
  username: string;
  full_name: string;
  is_admin: boolean;
  is_active: boolean;
  last_login_at: string | null;
  last_activity_at: string | null;
  created_at: string;
  total_consultas: number;
  total_ingestas: number;
  total_eventos: number;
}

export interface UserActivityItem {
  id: number;
  action: string;
  target_nit: string | null;
  target_factura: string | null;
  detail: string | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}
