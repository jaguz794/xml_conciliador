import type {
  ConciliacionResponse,
  DatabaseHealthResponse,
  FacturaDisponible,
  HealthResponse,
  ProcessedBatchResponse,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api";

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
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

  throw new Error(message);
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/salud`);
  return parseResponse<HealthResponse>(response);
}

export async function fetchDatabaseHealth(): Promise<DatabaseHealthResponse> {
  const response = await fetch(`${API_BASE_URL}/salud/db`);
  return parseResponse<DatabaseHealthResponse>(response);
}

export async function fetchInvoices(params: {
  nit?: string;
  factura?: string;
  limit?: number;
}): Promise<FacturaDisponible[]> {
  const query = new URLSearchParams();
  if (params.nit) {
    query.set("nit", params.nit);
  }
  if (params.factura) {
    query.set("factura", params.factura);
  }
  query.set("limit", String(params.limit ?? 20));

  const response = await fetch(`${API_BASE_URL}/facturas?${query.toString()}`);
  return parseResponse<FacturaDisponible[]>(response);
}

export async function fetchReconciliation(
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
  );
  return parseResponse<ConciliacionResponse>(response);
}

export async function uploadInvoiceFile(file: File): Promise<ProcessedBatchResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/ingesta/archivo`, {
    method: "POST",
    body: formData,
  });

  return parseResponse<ProcessedBatchResponse>(response);
}

export async function scanFolder(moveProcessed = false): Promise<ProcessedBatchResponse> {
  const response = await fetch(`${API_BASE_URL}/ingesta/escanear-carpeta`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ move_processed: moveProcessed }),
  });

  return parseResponse<ProcessedBatchResponse>(response);
}
