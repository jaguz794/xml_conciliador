from fastapi import APIRouter

from backend.app.models.schemas import DatabaseHealthResponse, HealthResponse
from backend.app.services.health_service import get_api_health, get_database_health

router = APIRouter()


@router.get("", response_model=HealthResponse)
def health() -> HealthResponse:
    return get_api_health()


@router.get("/db", response_model=DatabaseHealthResponse)
def health_db() -> DatabaseHealthResponse:
    return get_database_health()

