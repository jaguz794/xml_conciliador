from backend.app.core.config import settings
from backend.app.db import get_cursor
from backend.app.models.schemas import DatabaseHealthResponse, HealthResponse


def get_api_health() -> HealthResponse:
    return HealthResponse(
        ok=True,
        app=settings.app_name,
        environment=settings.environment,
    )


def get_database_health() -> DatabaseHealthResponse:
    with get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT
                current_database() AS database,
                current_user AS user,
                inet_server_addr()::text AS host
            """
        )
        row = cursor.fetchone()

    return DatabaseHealthResponse(
        ok=True,
        database=row["database"],
        user=row["user"],
        host=row["host"] or settings.db_host,
    )
