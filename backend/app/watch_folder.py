import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from backend.app.core.config import settings
from backend.app.services.ingestion_service import SUPPORTED_SUFFIXES, process_file_path, scan_input_directory


class InvoiceFolderHandler(FileSystemEventHandler):
    def on_created(self, event) -> None:
        if event.is_directory:
            return

        path = Path(event.src_path)
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            return

        time.sleep(settings.watcher_copy_wait_seconds)
        process_file_path(path, move_processed=True)


def run_folder_watcher() -> None:
    if settings.watcher_scan_existing_on_startup:
        scan_input_directory(move_processed=True)

    observer = Observer()
    observer.schedule(InvoiceFolderHandler(), str(settings.input_dir), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()


if __name__ == "__main__":
    run_folder_watcher()
