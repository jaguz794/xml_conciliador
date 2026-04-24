import time

from backend.app.core.config import settings
from backend.app.services.ingestion_service import (
    is_supported_source_file,
    process_file_path,
    wait_for_file_ready,
)


def run_folder_consumer() -> None:
    poll_interval = max(settings.folder_consumer_poll_seconds, 1.0)

    while True:
        for path in sorted(settings.input_dir.iterdir()):
            if not is_supported_source_file(path):
                continue

            if not wait_for_file_ready(path):
                continue

            try:
                process_file_path(path, move_processed=True)
            except Exception as exc:
                print(f"Error procesando {path.name}: {exc}")

        time.sleep(poll_interval)


if __name__ == "__main__":
    run_folder_consumer()
