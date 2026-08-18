from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.app.api.dependencies import get_current_session
from backend.app.models.schemas import ConciliacionResponse, FacturaDisponible
from backend.app.services.reconciliation_service import get_reconciliation, list_available_invoices
from backend.app.services.auth_service import (
    ACTION_MISS_RECONCILIATION,
    ACTION_VIEW_RECONCILIATION,
    SessionContext,
    log_user_action,
)

router = APIRouter()


@router.get("/facturas", response_model=list[FacturaDisponible])
def get_invoices(
    nit: str | None = Query(default=None),
    factura: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    _: SessionContext = Depends(get_current_session),
) -> list[FacturaDisponible]:
    return list_available_invoices(limit=limit, nit=nit, factura=factura)


@router.get("/conciliaciones/{nit}/{factura}", response_model=ConciliacionResponse)
def get_invoice_reconciliation(
    request: Request,
    nit: str,
    factura: str,
    force_refresh: bool = Query(default=False),
    session: SessionContext = Depends(get_current_session),
) -> ConciliacionResponse:
    reconciliation = get_reconciliation(factura=factura, nit=nit, force_refresh=force_refresh)
    if reconciliation is None:
        log_user_action(
            session,
            action=ACTION_MISS_RECONCILIATION,
            request=request,
            target_nit=nit,
            target_factura=factura,
            detail=f"force_refresh={force_refresh}",
        )
        raise HTTPException(
            status_code=404,
            detail="No existe una factura almacenada con ese NIT y numero.",
        )
    log_user_action(
        session,
        action=ACTION_VIEW_RECONCILIATION,
        request=request,
        target_nit=nit,
        target_factura=factura,
        detail=f"force_refresh={force_refresh}",
    )
    return reconciliation
