import logging
import time

from backend.app.core.config import settings
from backend.app.services.ingestion_service import (
    is_supported_source_file,
    process_file_path,
    wait_for_file_ready,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


def run_folder_consumer() -> None:
    poll_interval = max(settings.folder_consumer_poll_seconds, 1.0)
    logger.info(
        "Consumidor de carpeta iniciado | input_dir=%s | poll=%ss | delete_zip=%s",
        settings.input_dir,
        poll_interval,
        settings.delete_processed_zip_immediately,
    )

    while True:
        files_detected = 0
        for path in sorted(settings.input_dir.iterdir()):
            if not is_supported_source_file(path):
                continue

            files_detected += 1

            if not wait_for_file_ready(path):
                logger.info("Archivo aun copiandose o no estable, se reintentara: %s", path.name)
                continue

            try:
                process_file_path(path, move_processed=True)
            except Exception as exc:
                logger.exception("Error procesando %s: %s", path.name, exc)

        if files_detected == 0:
            logger.info("Sin archivos pendientes en %s", settings.input_dir)

        time.sleep(poll_interval)


if __name__ == "__main__":
    run_folder_consumer()
