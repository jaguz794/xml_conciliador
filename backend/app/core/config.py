from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Conciliador XML API"
    environment: str = "development"
    api_prefix: str = "/api"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    db_host: str = "192.168.10.9"
    db_port: int = 5432
    db_name: str = "biable01"
    db_user: str = "postgres"
    db_password: str = "postgres"

    input_dir: Path = ROOT_DIR / "facturas_entrada"
    processed_dir: Path = ROOT_DIR / "facturas_procesadas"
    logs_dir: Path = ROOT_DIR / "logs"
    reconciliation_cache_dir: Path = ROOT_DIR / "cache" / "conciliaciones"
    watcher_scan_existing_on_startup: bool = False
    watcher_copy_wait_seconds: float = 2.0
    processed_zip_retention_days: int = 10

    @property
    def cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    settings.input_dir.mkdir(parents=True, exist_ok=True)
    settings.reconciliation_cache_dir.mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
