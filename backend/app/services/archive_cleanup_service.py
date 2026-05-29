from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ArchiveCleanupResult:
    scanned: int
    deleted: int
    kept: int
    deleted_files: list[str]


@dataclass
class RuntimeCleanupResult:
    processed_zips: ArchiveCleanupResult
    reconciliation_cache: ArchiveCleanupResult


def _cleanup_expired_files(
    *,
    target_dir: Path,
    retention_days: int,
    allowed_suffixes: set[str] | None = None,
    recursive: bool = False,
) -> ArchiveCleanupResult:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    result = ArchiveCleanupResult(scanned=0, deleted=0, kept=0, deleted_files=[])
    target_dir.mkdir(parents=True, exist_ok=True)

    candidates = sorted(target_dir.rglob("*")) if recursive else sorted(target_dir.iterdir())
    for path in candidates:
        if not path.is_file():
            continue
        if allowed_suffixes and path.suffix.lower() not in allowed_suffixes:
            continue

        result.scanned += 1
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

        if modified_at <= cutoff:
            path.unlink(missing_ok=True)
            result.deleted += 1
            result.deleted_files.append(str(path.relative_to(target_dir)))
        else:
            result.kept += 1

    return result


def cleanup_expired_processed_zips() -> ArchiveCleanupResult:
    result = _cleanup_expired_files(
        target_dir=settings.processed_dir,
        retention_days=settings.processed_zip_retention_days,
        allowed_suffixes={".zip"},
    )

    if result.deleted_files:
        logger.info("ZIP vencidos eliminados de procesados: %s", ", ".join(result.deleted_files))

    return result


def cleanup_expired_reconciliation_cache() -> ArchiveCleanupResult:
    result = _cleanup_expired_files(
        target_dir=settings.reconciliation_cache_dir,
        retention_days=settings.reconciliation_cache_retention_days,
        recursive=True,
    )

    if result.deleted_files:
        logger.info("Archivos de cache vencidos eliminados: %s", ", ".join(result.deleted_files))

    return result


def cleanup_expired_runtime_files() -> RuntimeCleanupResult:
    return RuntimeCleanupResult(
        processed_zips=cleanup_expired_processed_zips(),
        reconciliation_cache=cleanup_expired_reconciliation_cache(),
    )
