from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.router import api_router
from backend.app.core.config import settings
from backend.app.db import DatabaseUnavailableError

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API web para consultar conciliaciones XML vs ERP sin generar Excel.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.exception_handler(DatabaseUnavailableError)
async def database_unavailable_handler(_: Request, exc: DatabaseUnavailableError):
    return JSONResponse(
        status_code=503,
        content={
            "detail": str(exc),
            "type": "database_unavailable",
        },
    )


@app.get("/")
def root() -> dict[str, str]:
    return {
        "app": settings.app_name,
        "docs": "/docs",
        "api_prefix": settings.api_prefix,
    }
