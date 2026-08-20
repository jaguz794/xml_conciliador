from datetime import date, datetime
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


class AuthUser(BaseModel):
    id: int
    username: str
    full_name: str
    is_admin: bool
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    expires_at: datetime
    user: AuthUser


class CreateUserRequest(BaseModel):
    username: str
    full_name: str
    password: str
    is_admin: bool = False
    is_active: bool = True


class UpdateUserRequest(BaseModel):
    full_name: str | None = None
    password: str | None = None
    is_admin: bool | None = None
    is_active: bool | None = None


class UserSummary(BaseModel):
    id: int
    username: str
    full_name: str
    is_admin: bool
    is_active: bool
    last_login_at: datetime | None = None
    last_activity_at: datetime | None = None
    created_at: datetime
    total_consultas: int = 0
    total_ingestas: int = 0
    total_eventos: int = 0


class UserActivityItem(BaseModel):
    id: int
    action: str
    target_nit: str | None = None
    target_factura: str | None = None
    detail: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime


class UserDailyConsultationItem(BaseModel):
    date: date
    total_consultas: int = 0
