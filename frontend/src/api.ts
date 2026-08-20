import type {
  AuthUser,
  ConciliacionResponse,
  DatabaseHealthResponse,
  FacturaDisponible,
  HealthResponse,
  LoginResponse,
  ProcessedBatchResponse,
  UserActivityItem,
  UserDailyConsultationItem,
  UserSummary,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api";
const AUTH_TOKEN_STORAGE_KEY = "conciliador_auth_token";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function buildAuthHeaders(token?: string, extraHeaders?: HeadersInit): Headers {
  const headers = new Headers(extraHeaders);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    if (response.status === 204) {
      return undefined as T;
    }
    return response.json() as Promise<T>;
  }

  let message = "No fue posible completar la solicitud.";
  try {
    const payload = (await response.json()) as { detail?: string };
    if (payload.detail) {
      message = payload.detail;
    }
  } catch {
    message = response.statusText || message;
  }

  throw new ApiError(message, response.status);
}

export function getStoredAuthToken(): string | null {
  return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
}

export function persistAuthToken(token: string): void {
  window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
}

export function clearStoredAuthToken(): void {
  window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/salud`);
  return parseResponse<HealthResponse>(response);
}

export async function fetchDatabaseHealth(): Promise<DatabaseHealthResponse> {
  const response = await fetch(`${API_BASE_URL}/salud/db`);
  return parseResponse<DatabaseHealthResponse>(response);
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ username, password }),
  });
  return parseResponse<LoginResponse>(response);
}

export async function logout(token: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/auth/logout`, {
    method: "POST",
    headers: buildAuthHeaders(token),
  });
  return parseResponse<void>(response);
}

export async function fetchCurrentUser(token: string): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: buildAuthHeaders(token),
  });
  return parseResponse<AuthUser>(response);
}

export async function changePassword(token: string, currentPassword: string, newPassword: string): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/auth/change-password`, {
    method: "POST",
    headers: buildAuthHeaders(token, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
  return parseResponse<AuthUser>(response);
}

export async function fetchUsers(token: string): Promise<UserSummary[]> {
  const response = await fetch(`${API_BASE_URL}/auth/users`, {
    headers: buildAuthHeaders(token),
  });
  return parseResponse<UserSummary[]>(response);
}

export async function fetchUserActivity(
  token: string,
  userId: number,
  limit = 50,
): Promise<UserActivityItem[]> {
  const query = new URLSearchParams({ limit: String(limit) });
  const response = await fetch(`${API_BASE_URL}/auth/users/${userId}/activity?${query.toString()}`, {
    headers: buildAuthHeaders(token),
  });
  return parseResponse<UserActivityItem[]>(response);
}

export async function fetchUserDailyConsultations(
  token: string,
  userId: number,
  limit = 30,
): Promise<UserDailyConsultationItem[]> {
  const query = new URLSearchParams({ limit: String(limit) });
  const response = await fetch(`${API_BASE_URL}/auth/users/${userId}/daily-consultations?${query.toString()}`, {
    headers: buildAuthHeaders(token),
  });
  return parseResponse<UserDailyConsultationItem[]>(response);
}

export async function createUser(
  token: string,
  payload: {
    username: string;
    full_name: string;
    password: string;
    is_admin: boolean;
    is_active: boolean;
    must_change_password: boolean;
  },
): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/auth/users`, {
    method: "POST",
    headers: buildAuthHeaders(token, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });
  return parseResponse<AuthUser>(response);
}

export async function updateUser(
  token: string,
  userId: number,
  payload: {
    full_name?: string;
    password?: string;
    is_admin?: boolean;
    is_active?: boolean;
    must_change_password?: boolean;
  },
): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/auth/users/${userId}`, {
    method: "PATCH",
    headers: buildAuthHeaders(token, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });
  return parseResponse<AuthUser>(response);
}

export async function fetchInvoices(
  token: string,
  params: {
    nit?: string;
    factura?: string;
    limit?: number;
  },
): Promise<FacturaDisponible[]> {
  const query = new URLSearchParams();
  if (params.nit) {
    query.set("nit", params.nit);
  }
  if (params.factura) {
    query.set("factura", params.factura);
  }
  query.set("limit", String(params.limit ?? 20));

  const response = await fetch(`${API_BASE_URL}/facturas?${query.toString()}`, {
    headers: buildAuthHeaders(token),
  });
  return parseResponse<FacturaDisponible[]>(response);
}

export async function fetchReconciliation(
  token: string,
  nit: string,
  factura: string,
  forceRefresh = false,
): Promise<ConciliacionResponse> {
  const query = new URLSearchParams();
  if (forceRefresh) {
    query.set("force_refresh", "true");
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  const response = await fetch(
    `${API_BASE_URL}/conciliaciones/${encodeURIComponent(nit)}/${encodeURIComponent(factura)}${suffix}`,
    {
      headers: buildAuthHeaders(token),
    },
  );
  return parseResponse<ConciliacionResponse>(response);
}

export async function uploadInvoiceFile(token: string, file: File): Promise<ProcessedBatchResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/ingesta/archivo`, {
    method: "POST",
    headers: buildAuthHeaders(token),
    body: formData,
  });

  return parseResponse<ProcessedBatchResponse>(response);
}

export async function scanFolder(token: string, moveProcessed = false): Promise<ProcessedBatchResponse> {
  const response = await fetch(`${API_BASE_URL}/ingesta/escanear-carpeta`, {
    method: "POST",
    headers: buildAuthHeaders(token, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({ move_processed: moveProcessed }),
  });

  return parseResponse<ProcessedBatchResponse>(response);
}
