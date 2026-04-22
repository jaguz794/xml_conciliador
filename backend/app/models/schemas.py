from typing import Any

from pydantic import BaseModel, Field


class DatabaseHealthResponse(BaseModel):
    ok: bool
    database: str
    user: str
    host: str


class HealthResponse(BaseModel):
    ok: bool
    app: str
    environment: str


class FacturaDisponible(BaseModel):
    factura: str
    nit: str
    lineas_xml: int


class TableSummaryItem(BaseModel):
    label: str
    value: float


class TablePayload(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    totals: dict[str, Any] = Field(default_factory=dict)
    summary: list[TableSummaryItem] = Field(default_factory=list)


class DashboardMetric(BaseModel):
    xml: float
    erp: float
    diferencia: float
    ajuste_ac: float = 0.0
    ajuste_np: float = 0.0
    ajuste_sugerido: float
    saldo: float


class DashboardPayload(BaseModel):
    titulo: str
    requiere_validacion: bool
    total_items: int
    items_con_diferencia: int
    alertas_rescate: int
    conteos_estado: dict[str, int] = Field(default_factory=dict)
    costo: DashboardMetric
    unidades: DashboardMetric


class ConciliacionResponse(BaseModel):
    factura: str
    nit: str
    dashboard: DashboardPayload
    detalle: TablePayload
    ac: TablePayload
    np: TablePayload


class ProcessedInvoice(BaseModel):
    factura: str
    nit: str
    lineas_xml: int
    origen: str


class ProcessedBatchResponse(BaseModel):
    procesadas: list[ProcessedInvoice]
    total_procesadas: int


class ScanFolderRequest(BaseModel):
    move_processed: bool = False
