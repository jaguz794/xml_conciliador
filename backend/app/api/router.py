from fastapi import APIRouter

from backend.app.api.routes import auth, health, ingestion, invoices

api_router = APIRouter()
api_router.include_router(health.router, prefix="/salud", tags=["Salud"])
api_router.include_router(auth.router, tags=["Autenticacion"])
api_router.include_router(ingestion.router, prefix="/ingesta", tags=["Ingesta"])
api_router.include_router(invoices.router, tags=["Facturas"])

