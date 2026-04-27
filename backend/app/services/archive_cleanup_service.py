from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ArchiveCleanupResult:
    scanned: int
    deleted: int
    kept: int
    deleted_files: list[str]


def cleanup_expired_processed_zips() -> ArchiveCleanupResult:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.processed_zip_retention_days)
    result = ArchiveCleanupResult(scanned=0, deleted=0, kept=0, deleted_files=[])
    settings.processed_dir.mkdir(parents=True, exist_ok=True)

    for path in sorted(settings.processed_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() != ".zip":
            continue

        result.scanned += 1
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

        if modified_at <= cutoff:
            path.unlink(missing_ok=True)
            result.deleted += 1
            result.deleted_files.append(path.name)
        else:
            result.kept += 1

    if result.deleted_files:
        logger.info("ZIP vencidos eliminados de procesados: %s", ", ".join(result.deleted_files))

    return result
