import io
import shutil
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


def process_file_path(path: Path, move_processed: bool = False) -> ProcessedBatchResponse:
    content = path.read_bytes()
    result = process_uploaded_file(path.name, content)

    if move_processed:
        _move_to_processed(path, result.procesadas)
        cleanup_expired_processed_zips()

    return result


def scan_input_directory(move_processed: bool = False) -> ProcessedBatchResponse:
    processed: list[ProcessedInvoice] = []

    for path in sorted(settings.input_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue

        batch = process_file_path(path, move_processed=move_processed)
        processed.extend(batch.procesadas)

    return ProcessedBatchResponse(
        procesadas=processed,
        total_procesadas=len(processed),
    )
