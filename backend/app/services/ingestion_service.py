import io
import shutil
import time
import uuid
import zipfile
from pathlib import Path

from backend.app.core.config import settings
from backend.app.db import get_cursor
from backend.app.models.schemas import ProcessedBatchResponse, ProcessedInvoice
from backend.app.services.archive_cleanup_service import cleanup_expired_processed_zips
from backend.app.services.reconciliation_service import build_and_cache_reconciliation, invalidate_reconciliation_cache
from backend.app.services.xml_service import parse_invoice_xml

SUPPORTED_SUFFIXES = {".xml", ".zip"}


def is_supported_source_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES


def wait_for_file_ready(path: Path) -> bool:
    if not path.exists():
        return False

    initial_wait = max(settings.watcher_copy_wait_seconds, 0)
    if initial_wait:
        time.sleep(initial_wait)

    deadline = time.monotonic() + max(settings.watcher_ready_timeout_seconds, 1.0)
    stable_checks_required = max(settings.watcher_stable_checks, 1)
    poll_interval = max(settings.watcher_poll_interval_seconds, 0.5)
    last_signature: tuple[int, int] | None = None
    stable_checks = 0

    while time.monotonic() <= deadline:
        if not path.exists() or not path.is_file():
            return False

        try:
            stat = path.stat()
        except OSError:
            time.sleep(poll_interval)
            continue

        signature = (stat.st_size, stat.st_mtime_ns)
        if stat.st_size > 0 and signature == last_signature:
            stable_checks += 1
        else:
            last_signature = signature
            stable_checks = 1 if stat.st_size > 0 else 0

        if stable_checks >= stable_checks_required:
            return True

        time.sleep(poll_interval)

    return False


def _clear_invoice(factura: str, nit: str) -> None:
    with get_cursor() as (connection, cursor):
        cursor.execute(
            """
            DELETE FROM factura_xml_detalle
            WHERE numero_factura = %s
            AND nit_proveedor = %s
            """,
            (factura, nit),
        )
        connection.commit()


def _insert_detail(detail: list[dict]) -> None:
    if not detail:
        return

    with get_cursor() as (connection, cursor):
        cursor.executemany(
            """
            INSERT INTO factura_xml_detalle
            (
                numero_factura,
                nit_proveedor,
                item_xml,
                codigo_barras,
                descripcion,
                cantidad,
                precio_unitario,
                imp_netos,
                impoconsumo,
                descuento,
                total
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    row["factura"],
                    row["nit"],
                    row.get("item_xml"),
                    row.get("codigo_barras"),
                    row.get("descripcion"),
                    row.get("cantidad", 0),
                    row.get("precio", 0),
                    row.get("imp_netos", 0),
                    row.get("impoconsumo", 0),
                    row.get("descuento", 0),
                    row.get("total", 0),
                )
                for row in detail
            ],
        )
        connection.commit()


def _process_xml_bytes(content: bytes, source_name: str) -> list[ProcessedInvoice]:
    factura, nit, detail = parse_invoice_xml(content)
    if not factura or not nit:
        return []

    invalidate_reconciliation_cache(factura, nit)
    _clear_invoice(factura, nit)
    _insert_detail(detail)
    try:
        build_and_cache_reconciliation(factura, nit)
    except Exception:
        pass

    return [
        ProcessedInvoice(
            factura=factura,
            nit=nit,
            lineas_xml=len(detail),
            origen=source_name,
        )
    ]


def _process_zip_bytes(content: bytes) -> list[ProcessedInvoice]:
    processed: list[ProcessedInvoice] = []

    with zipfile.ZipFile(io.BytesIO(content), "r") as compressed:
        for item in compressed.infolist():
            if item.is_dir():
                continue

            nested_name = item.filename
            nested_content = compressed.read(item)
            nested_suffix = Path(nested_name).suffix.lower()

            if nested_suffix == ".xml":
                processed.extend(_process_xml_bytes(nested_content, nested_name))
            elif nested_suffix == ".zip":
                processed.extend(_process_zip_bytes(nested_content))

    return processed


def process_uploaded_file(filename: str, content: bytes) -> ProcessedBatchResponse:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError("Solo se permiten archivos XML o ZIP.")

    try:
        if suffix == ".zip":
            processed = _process_zip_bytes(content)
        else:
            processed = _process_xml_bytes(content, filename)
    except zipfile.BadZipFile as exc:
        raise ValueError("El archivo ZIP no es valido o esta corrupto.") from exc

    return ProcessedBatchResponse(
        procesadas=processed,
        total_procesadas=len(processed),
    )


def _build_processed_name(path: Path, processed: list[ProcessedInvoice]) -> str:
    if len(processed) == 1 and path.suffix.lower() == ".xml":
        only = processed[0]
        return f"{only.factura}_{only.nit}{path.suffix.lower()}"
    return path.name


def _move_to_processed(path: Path, processed: list[ProcessedInvoice]) -> None:
    target_name = _build_processed_name(path, processed)
    destination = settings.processed_dir / target_name
    if destination.exists():
        destination = settings.processed_dir / f"{destination.stem}_{uuid.uuid4().hex[:6]}{destination.suffix}"
    shutil.move(str(path), str(destination))


def _finalize_processed_source(path: Path, processed: list[ProcessedInvoice]) -> None:
    if path.suffix.lower() == ".zip" and settings.delete_processed_zip_immediately:
        path.unlink(missing_ok=True)
        return

    _move_to_processed(path, processed)


def process_file_path(path: Path, move_processed: bool = False) -> ProcessedBatchResponse:
    content = path.read_bytes()
    result = process_uploaded_file(path.name, content)

    if move_processed:
        _finalize_processed_source(path, result.procesadas)
        cleanup_expired_processed_zips()

    return result


def scan_input_directory(move_processed: bool = False) -> ProcessedBatchResponse:
    processed: list[ProcessedInvoice] = []

    for path in sorted(settings.input_dir.iterdir()):
        if not is_supported_source_file(path):
            continue

        batch = process_file_path(path, move_processed=move_processed)
        processed.extend(batch.procesadas)

    return ProcessedBatchResponse(
        procesadas=processed,
        total_procesadas=len(processed),
    )
