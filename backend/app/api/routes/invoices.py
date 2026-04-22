from fastapi import APIRouter, HTTPException, Query

from backend.app.models.schemas import ConciliacionResponse, FacturaDisponible
from backend.app.services.reconciliation_service import get_reconciliation, list_available_invoices

router = APIRouter()


@router.get("/facturas", response_model=list[FacturaDisponible])
def get_invoices(
    nit: str | None = Query(default=None),
    factura: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[FacturaDisponible]:
    return list_available_invoices(limit=limit, nit=nit, factura=factura)


@router.get("/conciliaciones/{nit}/{factura}", response_model=ConciliacionResponse)
def get_invoice_reconciliation(
    nit: str,
    factura: str,
    force_refresh: bool = Query(default=False),
) -> ConciliacionResponse:
    reconciliation = get_reconciliation(factura=factura, nit=nit, force_refresh=force_refresh)
    if reconciliation is None:
        raise HTTPException(
            status_code=404,
            detail="No existe una factura almacenada con ese NIT y numero.",
        )
    return reconciliation
