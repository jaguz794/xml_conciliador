import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from backend.app.core.config import settings
from backend.app.services.ingestion_service import (
    is_supported_source_file,
    process_file_path,
    scan_input_directory,
    wait_for_file_ready,
)


class InvoiceFolderHandler(FileSystemEventHandler):
    def _process_candidate(self, path: Path) -> None:
        if not is_supported_source_file(path):
            return

        if not wait_for_file_ready(path):
            return

        process_file_path(path, move_processed=True)

    def on_created(self, event) -> None:
        if event.is_directory:
            return

        self._process_candidate(Path(event.src_path))

    def on_moved(self, event) -> None:
        if event.is_directory:
            return

        self._process_candidate(Path(event.dest_path))


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
