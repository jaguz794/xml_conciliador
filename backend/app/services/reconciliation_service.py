import json
import re
from decimal import Decimal
from difflib import SequenceMatcher
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import pandas as pd

from backend.app.core.config import settings
from backend.app.db import DatabaseUnavailableError, get_cursor
from backend.app.models.schemas import (
    ConciliacionResponse,
    DashboardMetric,
    DashboardPayload,
    FacturaDisponible,
    TablePayload,
    TableSummaryItem,
)

COMPARISON_SQL = """
WITH xml_base AS (
    SELECT
        x.codigo_barras,
        x.item_xml,
        x.descripcion,
        x.cantidad,
        COALESCE(ROUND(x.total / NULLIF(x.cantidad, 0)), 0) AS precio_unitario,
        x.imp_netos,
        x.impoconsumo,
        x.total,
        x.numero_factura,
        x.nit_proveedor,
        (
            SELECT TRIM(h.item_erp)
            FROM homologacion_items h
            WHERE h.nit_prov = x.nit_proveedor
              AND TRIM(h.item_prov) = TRIM(x.item_xml)
              AND x.item_xml <> ''
            LIMIT 1
        ) AS m_hom_prov_exacto,
        (
            SELECT TRIM(h.item_erp)
            FROM homologacion_items h
            WHERE h.nit_prov = x.nit_proveedor
              AND TRIM(h.cod_barras) = TRIM(x.codigo_barras)
              AND x.codigo_barras <> ''
            LIMIT 1
        ) AS m_hom_barras_exacto,
        (
            SELECT MAX(TRIM(cb.id_items))
            FROM cod_barras cb
            WHERE TRIM(cb.id_codbar) = TRIM(x.codigo_barras)
              AND x.codigo_barras <> ''
        ) AS m_multi_barras_exacto,
        (
            SELECT MAX(TRIM(i.id_item))
            FROM items i
            WHERE TRIM(i.id_codbar) = TRIM(x.codigo_barras)
              AND x.codigo_barras <> ''
        ) AS m_items_barras_exacto,
        (
            SELECT TRIM(h.item_erp)
            FROM homologacion_items h
            WHERE h.nit_prov = x.nit_proveedor
              AND LTRIM(TRIM(h.item_prov), '0') = LTRIM(TRIM(x.item_xml), '0')
              AND x.item_xml <> ''
            LIMIT 1
        ) AS m_hom_prov_rescate,
        (
            SELECT TRIM(h.item_erp)
            FROM homologacion_items h
            WHERE h.nit_prov = x.nit_proveedor
              AND LTRIM(TRIM(h.cod_barras), '0') = LTRIM(TRIM(x.codigo_barras), '0')
              AND x.codigo_barras <> ''
            LIMIT 1
        ) AS m_hom_barras_rescate,
        (
            SELECT MAX(TRIM(cb.id_items))
            FROM cod_barras cb
            WHERE LTRIM(TRIM(cb.id_codbar), '0') = LTRIM(TRIM(x.codigo_barras), '0')
              AND x.codigo_barras <> ''
        ) AS m_multi_barras_rescate,
        (
            SELECT MAX(TRIM(i.id_item))
            FROM items i
            WHERE LTRIM(TRIM(i.id_codbar), '0') = LTRIM(TRIM(x.codigo_barras), '0')
              AND x.codigo_barras <> ''
        ) AS m_items_barras_rescate
    FROM factura_xml_detalle x
    WHERE x.numero_factura = %s
      AND x.nit_proveedor = %s
),
xml_data AS (
    SELECT
        *,
        COALESCE(
            m_hom_prov_exacto,
            m_hom_barras_exacto,
            m_multi_barras_exacto,
            m_items_barras_exacto,
            m_hom_prov_rescate,
            m_hom_barras_rescate,
            m_multi_barras_rescate,
            m_items_barras_rescate
        ) AS item_erp_resuelto,
        CASE
            WHEN COALESCE(m_hom_prov_exacto, m_hom_barras_exacto, m_multi_barras_exacto, m_items_barras_exacto) IS NOT NULL THEN ''
            WHEN COALESCE(m_hom_prov_rescate, m_hom_barras_rescate, m_multi_barras_rescate, m_items_barras_rescate) IS NOT NULL THEN 'RESCATE CEROS'
            ELSE ''
        END AS alerta_cruce
    FROM xml_base
),
erp_data AS (
    SELECT
        TRIM(MAX(i.id_codbar)) AS codigo_barras,
        TRIM(i.id_item) AS item_erp_original,
        MAX(i.descripcion) AS descripcion_erp,
        SUM(ROUND(COALESCE(mov.cantidad_1, 0))) AS cantidad,
        COALESCE(
            ROUND(
                SUM(COALESCE(mov.vlr_bruto, 0)) / NULLIF(SUM(COALESCE(mov.cantidad_1, 0)), 0)
            ),
            0
        ) AS precio_uni,
        SUM(ROUND(COALESCE(mov.vlr_iva, 0))) AS imp_netos,
        SUM(ROUND(COALESCE(mov.vlr_impo, 0))) AS impoconsumo,
        SUM(ROUND(COALESCE(mov.vlr_bruto, 0))) AS tot_compra
    FROM cmmovimiento_inventario mov
    INNER JOIN items i
        ON mov.id_item = i.id_item
    WHERE mov.id_terc = %s
      AND TRIM(mov.doc_inv_tipo) = 'EA'
      AND LENGTH(TRIM(mov.documento_alt)) > 3
      AND %s LIKE '%%' || TRIM(mov.documento_alt)
    GROUP BY i.id_item
)
SELECT
    COALESCE(x.codigo_barras, e.codigo_barras) AS codigo_barras,
    x.item_xml AS item_xml,
    COALESCE(e.item_erp_original, x.item_erp_resuelto) AS item_erp,
    x.descripcion AS descripcion_xml,
    e.descripcion_erp AS descripcion_erp,
    CASE
        WHEN x.descripcion IS NULL THEN 'FALTA EN XML'
        WHEN e.item_erp_original IS NULL THEN 'FALTA EN ERP'
        WHEN COALESCE(x.cantidad, 0) <> COALESCE(e.cantidad, 0) THEN 'DIFERENCIA CANTIDAD'
        WHEN ABS(COALESCE(x.precio_unitario, 0) - COALESCE(e.precio_uni, 0)) > 1 THEN 'DIFERENCIA PRECIO'
        WHEN ABS(COALESCE(x.imp_netos, 0) - COALESCE(e.imp_netos, 0)) > 5 THEN 'DIFERENCIA IVA'
        WHEN ABS(COALESCE(x.impoconsumo, 0) - COALESCE(e.impoconsumo, 0)) > 5 THEN 'DIFERENCIA ICUI'
        WHEN ABS(COALESCE(x.total, 0) - COALESCE(e.tot_compra, 0)) > 0.01 THEN 'DIFERENCIA TOTAL'
        ELSE 'OK'
    END AS estado,
    COALESCE(x.alerta_cruce, '') AS alerta_cruce,
    COALESCE(x.cantidad, 0) AS xml_cant,
    COALESCE(e.cantidad, 0) AS erp_cant,
    (COALESCE(x.cantidad, 0) - COALESCE(e.cantidad, 0)) AS dif_cant,
    COALESCE(x.precio_unitario, 0) AS xml_precio,
    COALESCE(e.precio_uni, 0) AS erp_precio,
    (COALESCE(x.precio_unitario, 0) - COALESCE(e.precio_uni, 0)) AS dif_precio,
    COALESCE(x.imp_netos, 0) AS xml_iva,
    COALESCE(e.imp_netos, 0) AS erp_iva,
    (COALESCE(x.imp_netos, 0) - COALESCE(e.imp_netos, 0)) AS dif_iva,
    COALESCE(x.impoconsumo, 0) AS xml_icui,
    COALESCE(e.impoconsumo, 0) AS erp_icui,
    (COALESCE(x.impoconsumo, 0) - COALESCE(e.impoconsumo, 0)) AS dif_icui,
    COALESCE(x.total, 0) AS xml_total,
    COALESCE(e.tot_compra, 0) AS erp_total,
    (COALESCE(x.total, 0) - COALESCE(e.tot_compra, 0)) AS dif_total
FROM xml_data x
FULL OUTER JOIN erp_data e
    ON LTRIM(TRIM(CAST(x.item_erp_resuelto AS VARCHAR)), '0') =
       LTRIM(TRIM(CAST(e.item_erp_original AS VARCHAR)), '0')
ORDER BY estado DESC, codigo_barras ASC
"""

CACHE_VERSION = "v9"
GLOBAL_TOTAL_TOLERANCE = 1

PACKAGE_FACTOR_PATTERN = re.compile(
    r"(?<!\d)(\d{1,3})(?:UND|UNID|UN|U)(?=X|\b)",
    re.IGNORECASE,
)

SIZE_TOKEN_PATTERN = re.compile(
    r"(\d+(?:[.,]\d+)?)(?:G|GR|GRS|ML)",
    re.IGNORECASE,
)

DESCRIPTION_TOKEN_PATTERN = re.compile(r"[A-Z0-9]+")

PACKAGING_DESCRIPTION_TOKENS = {
    "BJA",
    "BJAS",
    "BLS",
    "BOL",
    "BOLS",
    "BOLSA",
    "BOLSAS",
    "CAJA",
    "CAJAS",
    "CJ",
    "CJA",
    "DP",
    "DPACK",
    "DPCK",
    "PACK",
    "PCK",
    "PL",
    "PLE",
    "PLEG",
    "PLEGX",
    "PLEX",
    "PLG",
    "PLGX",
    "PLX",
    "UD",
    "UDS",
    "UDX",
    "UN",
    "UND",
    "UNID",
    "UNX",
    "UX",
    "X",
}

PACKAGING_ALERT = "CRUCE EMPAQUE"

ERP_SIDE_COLUMNS = [
    "item_erp",
    "descripcion_erp",
    "erp_cant",
    "erp_precio",
    "erp_iva",
    "erp_icui",
    "erp_total",
]

DETAIL_INTERNAL_COLUMNS = {
    "xml_cant_original",
    "xml_factor_empaque",
}

AC_COLUMNS = [
    "ITEM_XML",
    "ITEM_ERP",
    "DESCRIPCION_XML",
    "DESCRIPCION_ERP",
    "CANTIDAD_XML",
    "CANTIDAD_ERP",
    "TOTAL_XML",
    "TOTAL_ERP",
    "DIF_COSTO_UND",
    "COSTO_DIF_TOTAL",
    "ORIGEN_AJUSTE",
]

NUMERIC_COLUMNS = [
    "xml_cant",
    "erp_cant",
    "dif_cant",
    "xml_precio",
    "erp_precio",
    "dif_precio",
    "xml_iva",
    "erp_iva",
    "dif_iva",
    "xml_icui",
    "erp_icui",
    "dif_icui",
    "xml_total",
    "erp_total",
    "dif_total",
]


def _round_number(value: float) -> float:
    return round(float(value), 2)


def _float_value(value: Any) -> float:
    if value is None or pd.isna(value):
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _text_value(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _serialize_scalar(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return _round_number(value)
    if isinstance(value, Decimal):
        return _round_number(float(value))
    if hasattr(value, "item"):
        native_value = value.item()
        if isinstance(native_value, Decimal):
            return _round_number(float(native_value))
        if isinstance(native_value, float):
            return _round_number(native_value)
        return native_value
    return value


def _table_from_dataframe(
    frame: pd.DataFrame,
    totals: dict[str, Any] | None = None,
    summary: list[TableSummaryItem] | None = None,
) -> TablePayload:
    rows = []
    for record in frame.to_dict(orient="records"):
        rows.append({key: _serialize_scalar(value) for key, value in record.items()})
    serialized_totals = {
        key: _serialize_scalar(value)
        for key, value in (totals or {}).items()
    }
    return TablePayload(
        columns=list(frame.columns),
        rows=rows,
        totals=serialized_totals,
        summary=summary or [],
    )


def _invoice_exists(factura: str, nit: str) -> bool:
    with get_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM factura_xml_detalle
                WHERE numero_factura = %s
                  AND nit_proveedor = %s
            )
            """,
            (factura, nit),
        )
        return bool(cursor.fetchone()[0])


def _safe_cache_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", value.strip())


def _cache_file_path(factura: str, nit: str) -> Path:
    filename = f"{CACHE_VERSION}__{_safe_cache_key(nit)}__{_safe_cache_key(factura)}.json"
    return settings.reconciliation_cache_dir / filename


def _write_cache_file(path: Path, payload: ConciliacionResponse) -> None:
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp_file:
        json.dump(payload.model_dump(), tmp_file, ensure_ascii=False)
        temp_path = Path(tmp_file.name)
    temp_path.replace(path)


def invalidate_reconciliation_cache(factura: str, nit: str) -> None:
    cache_file = _cache_file_path(factura, nit)
    if cache_file.exists():
        cache_file.unlink()


def load_reconciliation_snapshot(factura: str, nit: str) -> ConciliacionResponse | None:
    cache_file = _cache_file_path(factura, nit)
    if not cache_file.exists():
        return None

    data = json.loads(cache_file.read_text(encoding="utf-8"))
    return ConciliacionResponse.model_validate(data)


def _list_cached_invoices(
    limit: int = 20,
    nit: str | None = None,
    factura: str | None = None,
) -> list[FacturaDisponible]:
    invoices: list[tuple[float, FacturaDisponible]] = []
    nit_filter = nit.strip().lower() if nit else None
    factura_filter = factura.strip().lower() if factura else None

    for cache_file in settings.reconciliation_cache_dir.glob(f"{CACHE_VERSION}__*.json"):
        try:
            payload = ConciliacionResponse.model_validate_json(cache_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        if nit_filter and nit_filter not in payload.nit.lower():
            continue
        if factura_filter and factura_filter not in payload.factura.lower():
            continue

        lineas_xml = len(
            [
                row
                for row in payload.detalle.rows
                if str(row.get("codigo_barras")) != "TOTAL FACTURA"
            ]
        )
        invoices.append(
            (
                cache_file.stat().st_mtime,
                FacturaDisponible(
                    factura=payload.factura,
                    nit=payload.nit,
                    lineas_xml=lineas_xml,
                ),
            )
        )

    invoices.sort(key=lambda item: item[0], reverse=True)
    return [invoice for _, invoice in invoices[:limit]]


def list_available_invoices(
    limit: int = 20,
    nit: str | None = None,
    factura: str | None = None,
) -> list[FacturaDisponible]:
    nit_filter = f"%{nit.strip()}%" if nit else None
    factura_filter = f"%{factura.strip()}%" if factura else None

    try:
        with get_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                """
                SELECT
                    numero_factura AS factura,
                    nit_proveedor AS nit,
                    COUNT(*)::int AS lineas_xml
                FROM factura_xml_detalle
                WHERE (%s IS NULL OR nit_proveedor ILIKE %s)
                  AND (%s IS NULL OR numero_factura ILIKE %s)
                GROUP BY numero_factura, nit_proveedor
                ORDER BY numero_factura DESC, nit_proveedor DESC
                LIMIT %s
                """,
                (nit_filter, nit_filter, factura_filter, factura_filter, limit),
            )
            rows = cursor.fetchall()
        return [FacturaDisponible(**row) for row in rows]
    except DatabaseUnavailableError:
        return _list_cached_invoices(limit=limit, nit=nit, factura=factura)


def _get_comparison_dataframe(factura: str, nit: str) -> pd.DataFrame:
    with get_cursor() as (_, cursor):
        cursor.execute(COMPARISON_SQL, (factura, nit, nit, factura))
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]

    return pd.DataFrame(rows, columns=columns)


def _append_total_row(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    total_row = {column: "" for column in frame.columns}
    total_row["codigo_barras"] = "TOTAL FACTURA"
    total_row["descripcion_xml"] = ">>> SUMA GLOBAL DE LA FACTURA <<<"

    for column in [
        "xml_cant",
        "erp_cant",
        "dif_cant",
        "xml_iva",
        "erp_iva",
        "dif_iva",
        "xml_icui",
        "erp_icui",
        "dif_icui",
        "xml_total",
        "erp_total",
        "dif_total",
    ]:
        total_row[column] = frame[column].sum()

    total_difference = float(total_row["dif_total"])
    total_row["estado"] = "OK" if abs(total_difference) <= GLOBAL_TOTAL_TOLERANCE else "DIFERENCIA TOTAL"
    total_row["xml_precio"] = 0
    total_row["erp_precio"] = 0
    total_row["dif_precio"] = 0

    return pd.concat([frame, pd.DataFrame([total_row])], ignore_index=True)


def _coerce_numeric_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    normalized = frame.copy()
    for column in NUMERIC_COLUMNS:
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    return normalized


def _description_tokens(description: Any) -> set[str]:
    raw_description = _text_value(description).upper()
    if not raw_description:
        return set()

    compact_description = re.sub(r"\s+", "", raw_description)
    tokens = {
        f"{match.group(1).replace(',', '.')}G"
        for match in SIZE_TOKEN_PATTERN.finditer(compact_description)
    }

    normalized_text = re.sub(r"[^A-Z0-9]+", " ", raw_description)
    for token in DESCRIPTION_TOKEN_PATTERN.findall(normalized_text):
        if token in PACKAGING_DESCRIPTION_TOKENS:
            continue
        if any(char.isdigit() for char in token):
            continue
        if len(token) < 3:
            continue
        tokens.add(token)

    return tokens


def _description_similarity(xml_description: Any, erp_description: Any) -> tuple[int, float]:
    xml_tokens = _description_tokens(xml_description)
    erp_tokens = _description_tokens(erp_description)
    if not xml_tokens or not erp_tokens:
        return 0, 0.0

    overlap = len(xml_tokens & erp_tokens)
    xml_text = " ".join(sorted(xml_tokens))
    erp_text = " ".join(sorted(erp_tokens))
    sequence_ratio = SequenceMatcher(None, xml_text, erp_text).ratio()
    return overlap, sequence_ratio


def _extract_package_factor(description: Any) -> int:
    normalized_description = re.sub(r"\s+", "", _text_value(description).upper())
    if not normalized_description:
        return 1

    matches = [int(match.group(1)) for match in PACKAGE_FACTOR_PATTERN.finditer(normalized_description)]
    valid_matches = [value for value in matches if value > 1]
    return valid_matches[-1] if valid_matches else 1


def _append_alert(existing_alert: Any, new_alert: str) -> str:
    existing_parts = [part.strip() for part in _text_value(existing_alert).split("|") if part.strip()]
    if new_alert not in existing_parts:
        existing_parts.append(new_alert)
    return " | ".join(existing_parts)


def _totals_close(xml_total: Any, erp_total: Any) -> bool:
    xml_total_value = abs(_float_value(xml_total))
    erp_total_value = abs(_float_value(erp_total))
    if xml_total_value <= 0 or erp_total_value <= 0:
        return False

    total_gap = abs(xml_total_value - erp_total_value)
    tolerance = max(max(xml_total_value, erp_total_value) * 0.02, 50)
    return total_gap <= tolerance


def _apply_xml_package_adjustment(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    adjusted = frame.copy()
    adjusted["xml_cant_original"] = adjusted["xml_cant"]
    adjusted["xml_factor_empaque"] = adjusted["descripcion_xml"].apply(_extract_package_factor).astype(int)
    return adjusted


def _infer_package_factor_from_matched_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    adjusted = frame.copy()
    for index, row in adjusted.iterrows():
        if not _text_value(row.get("descripcion_xml")) or not _text_value(row.get("descripcion_erp")):
            continue

        xml_original_qty = _float_value(row.get("xml_cant_original") or row.get("xml_cant"))
        erp_qty = _float_value(row.get("erp_cant"))
        if xml_original_qty <= 0 or erp_qty <= 0:
            continue

        inferred_factor = erp_qty / xml_original_qty
        rounded_factor = int(round(inferred_factor))
        if rounded_factor <= 1 or abs(inferred_factor - rounded_factor) > 0.01:
            continue
        if not _totals_close(row.get("xml_total"), row.get("erp_total")):
            continue

        current_factor = int(_float_value(row.get("xml_factor_empaque")) or 1)
        target_qty = xml_original_qty * rounded_factor
        current_qty = _float_value(row.get("xml_cant"))
        if rounded_factor <= current_factor and abs(current_qty - target_qty) <= 0.01:
            continue

        adjusted.at[index, "xml_factor_empaque"] = rounded_factor
        adjusted.at[index, "xml_cant"] = target_qty
        adjusted.at[index, "xml_precio"] = _float_value(row.get("xml_total")) / adjusted.at[index, "xml_cant"]
        adjusted.at[index, "alerta_cruce"] = _append_alert(row.get("alerta_cruce"), PACKAGING_ALERT)

    return adjusted


def _merge_packaging_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    adjusted = frame.copy().reset_index(drop=True)
    xml_only_indexes = adjusted.index[
        adjusted["descripcion_xml"].apply(_text_value).ne("")
        & adjusted["descripcion_erp"].apply(_text_value).eq("")
    ]
    erp_only_indexes = adjusted.index[
        adjusted["descripcion_xml"].apply(_text_value).eq("")
        & adjusted["descripcion_erp"].apply(_text_value).ne("")
    ]
    if len(xml_only_indexes) == 0 or len(erp_only_indexes) == 0:
        return adjusted

    used_erp_indexes: set[int] = set()
    rows_to_drop: list[int] = []

    for xml_index in xml_only_indexes:
        xml_row = adjusted.loc[xml_index]
        xml_original_qty = _float_value(xml_row.get("xml_cant_original") or xml_row.get("xml_cant"))
        if xml_original_qty <= 0:
            continue

        best_match_index: int | None = None
        best_factor = 1
        best_score: tuple[int, float, float] | None = None

        for erp_index in erp_only_indexes:
            if erp_index in used_erp_indexes:
                continue

            erp_row = adjusted.loc[erp_index]
            erp_qty = _float_value(erp_row.get("erp_cant"))
            if erp_qty <= 0:
                continue

            inferred_factor = erp_qty / xml_original_qty
            rounded_factor = int(round(inferred_factor))
            if rounded_factor <= 1 or abs(inferred_factor - rounded_factor) > 0.01:
                continue
            if not _totals_close(xml_row.get("xml_total"), erp_row.get("erp_total")):
                continue

            overlap, sequence_ratio = _description_similarity(
                xml_row.get("descripcion_xml"),
                erp_row.get("descripcion_erp"),
            )
            if overlap < 2 and sequence_ratio < 0.62:
                continue

            adjusted_xml_qty = xml_original_qty * rounded_factor
            adjusted_xml_price = _float_value(xml_row.get("xml_total")) / adjusted_xml_qty
            erp_price = _float_value(erp_row.get("erp_precio"))
            if erp_price > 0:
                price_tolerance = max(erp_price * 0.08, 5)
                if abs(adjusted_xml_price - erp_price) > price_tolerance and overlap < 3 and sequence_ratio < 0.72:
                    continue

            total_gap = abs(_float_value(xml_row.get("xml_total")) - _float_value(erp_row.get("erp_total")))
            score = (overlap, sequence_ratio, -total_gap)
            if best_score is None or score > best_score:
                best_match_index = erp_index
                best_factor = rounded_factor
                best_score = score

        if best_match_index is None:
            continue

        adjusted.at[xml_index, "xml_factor_empaque"] = max(
            int(_float_value(adjusted.at[xml_index, "xml_factor_empaque"]) or 1),
            best_factor,
        )
        adjusted.at[xml_index, "xml_cant"] = xml_original_qty * best_factor
        adjusted.at[xml_index, "xml_precio"] = (
            _float_value(adjusted.at[xml_index, "xml_total"]) / adjusted.at[xml_index, "xml_cant"]
        )

        for column in ERP_SIDE_COLUMNS:
            adjusted.at[xml_index, column] = adjusted.at[best_match_index, column]

        adjusted.at[xml_index, "item_erp"] = _text_value(adjusted.at[best_match_index, "item_erp"]) or adjusted.at[
            xml_index,
            "item_erp",
        ]
        adjusted.at[xml_index, "alerta_cruce"] = _append_alert(
            adjusted.at[xml_index, "alerta_cruce"],
            PACKAGING_ALERT,
        )

        used_erp_indexes.add(best_match_index)
        rows_to_drop.append(best_match_index)

    if not rows_to_drop:
        return adjusted

    return adjusted.drop(index=rows_to_drop).reset_index(drop=True)


def _compute_row_state(row: pd.Series) -> str:
    if not _text_value(row.get("descripcion_xml")):
        return "FALTA EN XML"
    if not _text_value(row.get("descripcion_erp")):
        return "FALTA EN ERP"
    if abs(float(row.get("dif_cant", 0) or 0)) > 0.01:
        return "DIFERENCIA CANTIDAD"
    if abs(float(row.get("dif_precio", 0) or 0)) > 1:
        return "DIFERENCIA PRECIO"
    if abs(float(row.get("dif_iva", 0) or 0)) > 5:
        return "DIFERENCIA IVA"
    if abs(float(row.get("dif_icui", 0) or 0)) > 5:
        return "DIFERENCIA ICUI"
    if abs(float(row.get("dif_total", 0) or 0)) > 0.01:
        return "DIFERENCIA TOTAL"
    return "OK"


def _recalculate_comparison_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    adjusted = frame.copy()
    adjusted["dif_cant"] = adjusted["xml_cant"] - adjusted["erp_cant"]
    adjusted["dif_precio"] = adjusted["xml_precio"] - adjusted["erp_precio"]
    adjusted["dif_iva"] = adjusted["xml_iva"] - adjusted["erp_iva"]
    adjusted["dif_icui"] = adjusted["xml_icui"] - adjusted["erp_icui"]
    adjusted["dif_total"] = adjusted["xml_total"] - adjusted["erp_total"]
    adjusted["estado"] = adjusted.apply(_compute_row_state, axis=1)
    return adjusted


def _compose_adjustment_origin(base_origin: str, xml_row: pd.Series | None, erp_row: pd.Series | None) -> str:
    alert_sources = []
    if xml_row is not None:
        alert_sources.append(_text_value(xml_row.get("alerta_cruce")))
    if erp_row is not None and erp_row is not xml_row:
        alert_sources.append(_text_value(erp_row.get("alerta_cruce")))
    if any(PACKAGING_ALERT in alert for alert in alert_sources):
        return f"{base_origin} | {PACKAGING_ALERT}"
    return base_origin


def _build_ac_explanation_row(
    xml_row: pd.Series | None,
    erp_row: pd.Series | None,
    origin: str,
    source_order: int,
) -> dict[str, Any]:
    xml_qty = _float_value(xml_row.get("xml_cant")) if xml_row is not None else 0.0
    erp_qty = _float_value(erp_row.get("erp_cant")) if erp_row is not None else 0.0
    xml_total = _float_value(xml_row.get("xml_total")) if xml_row is not None else 0.0
    erp_total = _float_value(erp_row.get("erp_total")) if erp_row is not None else 0.0
    effective_qty = max(xml_qty, erp_qty, 1.0)
    net_total = xml_total - erp_total

    return {
        "ITEM_XML": _text_value(xml_row.get("item_xml")) if xml_row is not None else None,
        "ITEM_ERP": _text_value(erp_row.get("item_erp")) if erp_row is not None else None,
        "DESCRIPCION_XML": _text_value(xml_row.get("descripcion_xml")) if xml_row is not None else None,
        "DESCRIPCION_ERP": _text_value(erp_row.get("descripcion_erp")) if erp_row is not None else None,
        "CANTIDAD_XML": xml_qty,
        "CANTIDAD_ERP": erp_qty,
        "TOTAL_XML": xml_total,
        "TOTAL_ERP": erp_total,
        "DIF_COSTO_UND": net_total / effective_qty,
        "COSTO_DIF_TOTAL": net_total,
        "ORIGEN_AJUSTE": origin,
        "_source_order": source_order,
    }


def _build_ac_explanation_frame(items_frame: pd.DataFrame) -> pd.DataFrame:
    if items_frame.empty:
        return pd.DataFrame(columns=AC_COLUMNS)

    working = items_frame.copy().reset_index(drop=True)
    xml_only_indexes = working.index[
        working["descripcion_xml"].apply(_text_value).ne("")
        & working["descripcion_erp"].apply(_text_value).eq("")
    ]
    erp_only_indexes = working.index[
        working["descripcion_xml"].apply(_text_value).eq("")
        & working["descripcion_erp"].apply(_text_value).ne("")
    ]

    pair_map: dict[int, int] = {}
    used_erp_indexes: set[int] = set()

    for xml_index in xml_only_indexes:
        xml_row = working.loc[xml_index]
        best_match_index: int | None = None
        best_score: tuple[int, float, float] | None = None

        for erp_index in erp_only_indexes:
            if erp_index in used_erp_indexes:
                continue

            erp_row = working.loc[erp_index]
            overlap, sequence_ratio = _description_similarity(
                xml_row.get("descripcion_xml"),
                erp_row.get("descripcion_erp"),
            )
            if overlap < 2 and sequence_ratio < 0.62:
                continue

            total_gap = abs(_float_value(xml_row.get("xml_total")) - _float_value(erp_row.get("erp_total")))
            score = (overlap, sequence_ratio, -total_gap)
            if best_score is None or score > best_score:
                best_match_index = erp_index
                best_score = score

        if best_match_index is None:
            continue

        pair_map[xml_index] = best_match_index
        used_erp_indexes.add(best_match_index)

    explanation_rows: list[dict[str, Any]] = []
    consumed_indexes: set[int] = set()

    for xml_index, erp_index in pair_map.items():
        explanation_rows.append(
            _build_ac_explanation_row(
                xml_row=working.loc[xml_index],
                erp_row=working.loc[erp_index],
                origin=_compose_adjustment_origin(
                    "CRUCE NETO ERP/XML",
                    working.loc[xml_index],
                    working.loc[erp_index],
                ),
                source_order=min(xml_index, erp_index),
            )
        )
        consumed_indexes.add(xml_index)
        consumed_indexes.add(erp_index)

    for index, row in working.iterrows():
        if index in consumed_indexes:
            continue

        xml_present = _text_value(row.get("descripcion_xml")) != ""
        erp_present = _text_value(row.get("descripcion_erp")) != ""
        if xml_present and erp_present:
            origin = "DIFERENCIA NETA ERP/XML"
            xml_row = row
            erp_row = row
        elif xml_present:
            origin = "SOLO XML"
            xml_row = row
            erp_row = None
        else:
            origin = "SOLO ERP"
            xml_row = None
            erp_row = row

        explanation_rows.append(
            _build_ac_explanation_row(
                xml_row=xml_row,
                erp_row=erp_row,
                origin=_compose_adjustment_origin(origin, xml_row, erp_row),
                source_order=index,
            )
        )

    if not explanation_rows:
        return pd.DataFrame(columns=AC_COLUMNS)

    ac_frame = pd.DataFrame(explanation_rows)
    ac_frame = ac_frame[abs(ac_frame["COSTO_DIF_TOTAL"]) >= 1]
    if ac_frame.empty:
        return pd.DataFrame(columns=AC_COLUMNS)

    ac_frame = ac_frame.sort_values(by=["_source_order", "ITEM_XML", "ITEM_ERP"], na_position="last")
    return ac_frame.drop(columns="_source_order").reset_index(drop=True)


def _detect_packaging(frame: pd.DataFrame) -> pd.Series:
    xml_qty = frame["xml_cant"].abs()
    erp_qty = frame["erp_cant"].abs()
    qty_gap = (frame["xml_cant"] - frame["erp_cant"]).abs()

    positive_qty = pd.concat(
        [xml_qty.replace(0, float("nan")), erp_qty.replace(0, float("nan"))],
        axis=1,
    )
    min_qty = positive_qty.min(axis=1).fillna(1)

    xml_price = frame["xml_precio"].abs()
    erp_price = frame["erp_precio"].abs()
    positive_prices = pd.concat(
        [xml_price.replace(0, float("nan")), erp_price.replace(0, float("nan"))],
        axis=1,
    )
    min_price = positive_prices.min(axis=1).fillna(1)
    max_price = pd.concat([xml_price, erp_price], axis=1).max(axis=1).fillna(0)
    price_ratio = max_price / min_price

    total_reference = pd.concat(
        [frame["xml_total"].abs(), frame["erp_total"].abs()],
        axis=1,
    ).max(axis=1).fillna(0)
    total_tolerance = total_reference.mul(0.02).clip(lower=50)

    return (
        (qty_gap >= (min_qty * 2))
        & (price_ratio >= 2)
        & (frame["dif_total"].abs() <= total_tolerance)
        & (xml_qty > 0)
        & (erp_qty > 0)
    )


def _build_reconciliation_payload(factura: str, nit: str) -> ConciliacionResponse:
    raw_frame = _get_comparison_dataframe(factura, nit)
    items_frame = _coerce_numeric_columns(raw_frame.copy())
    items_frame = _apply_xml_package_adjustment(items_frame)
    items_frame = _infer_package_factor_from_matched_rows(items_frame)
    items_frame = _merge_packaging_rows(items_frame)
    items_frame = _recalculate_comparison_columns(items_frame)
    detail_frame = _append_total_row(
        items_frame.drop(columns=[column for column in DETAIL_INTERNAL_COLUMNS if column in items_frame.columns]).copy()
    )
    packaging_mask = _detect_packaging(items_frame)

    np_frame = items_frame.copy()
    np_frame["DIF_UND_FISICA"] = np_frame["xml_cant"] - np_frame["erp_cant"]
    np_frame["AJUSTE_UND_SUGERIDO"] = np_frame["DIF_UND_FISICA"].where(~packaging_mask, 0)
    np_frame["OBSERVACION"] = packaging_mask.map(
        lambda detected: "EMPAQUE DETECTADO - NO GENERA NP"
        if detected
        else "NOTA PROVEEDOR"
    )
    np_frame = np_frame[
        [
            "item_xml",
            "item_erp",
            "descripcion_xml",
            "descripcion_erp",
            "erp_cant",
            "xml_cant",
            "DIF_UND_FISICA",
            "AJUSTE_UND_SUGERIDO",
            "OBSERVACION",
        ]
    ]
    np_frame.columns = [
        "ITEM_XML",
        "ITEM_ERP",
        "DESCRIPCION_XML",
        "DESCRIPCION_ERP",
        "CANTIDAD_ERP",
        "CANTIDAD_XML",
        "DIF_UND_FISICA",
        "AJUSTE_UND_SUGERIDO",
        "OBSERVACION",
    ]
    np_frame = np_frame[abs(np_frame["DIF_UND_FISICA"]) > 0]

    ac_frame = _build_ac_explanation_frame(items_frame)

    valor_xml = float(items_frame["xml_total"].sum())
    valor_erp = float(items_frame["erp_total"].sum())
    dif_valor = valor_xml - valor_erp

    cant_xml = float(items_frame["xml_cant"].sum())
    cant_erp = float(items_frame["erp_cant"].sum())
    dif_cant = cant_xml - cant_erp

    ajuste_costo_ac = float(ac_frame["COSTO_DIF_TOTAL"].sum()) if not ac_frame.empty else 0.0
    total_ajuste_costo = ajuste_costo_ac
    saldo_dif_costo = dif_valor - total_ajuste_costo

    ajuste_cant_np = float(np_frame["AJUSTE_UND_SUGERIDO"].sum()) if not np_frame.empty else 0.0
    saldo_dif_cant = dif_cant - ajuste_cant_np

    title = (
        "NECESARIO VALIDACION MANUAL"
        if abs(dif_valor) > GLOBAL_TOTAL_TOLERANCE or abs(dif_cant) > 0
        else "CUADRE PERFECTO - SIN ACCION REQUERIDA"
    )

    state_counts = {
        str(key): int(value)
        for key, value in items_frame["estado"].fillna("SIN ESTADO").value_counts().to_dict().items()
    }

    dashboard = DashboardPayload(
        titulo=title,
        requiere_validacion=title != "CUADRE PERFECTO - SIN ACCION REQUERIDA",
        total_items=len(items_frame),
        items_con_diferencia=int((items_frame["estado"] != "OK").sum()),
        alertas_rescate=int(items_frame["alerta_cruce"].fillna("").astype(str).str.contains("RESCATE CEROS").sum()),
        conteos_estado=state_counts,
        costo=DashboardMetric(
            xml=_round_number(valor_xml),
            erp=_round_number(valor_erp),
            diferencia=_round_number(dif_valor),
            ajuste_ac=_round_number(ajuste_costo_ac),
            ajuste_np=0.0,
            ajuste_sugerido=_round_number(total_ajuste_costo),
            saldo=_round_number(saldo_dif_costo),
        ),
        unidades=DashboardMetric(
            xml=_round_number(cant_xml),
            erp=_round_number(cant_erp),
            diferencia=_round_number(dif_cant),
            ajuste_ac=0.0,
            ajuste_np=_round_number(ajuste_cant_np),
            ajuste_sugerido=_round_number(ajuste_cant_np),
            saldo=_round_number(saldo_dif_cant),
        ),
    )

    ac_totals = {
        "ITEM_XML": "TOTAL",
        "COSTO_DIF_TOTAL": ajuste_costo_ac,
    }
    np_totals = {
        "ITEM_XML": "TOTAL",
        "AJUSTE_UND_SUGERIDO": ajuste_cant_np,
    }
    ac_summary = [
        TableSummaryItem(label="Total neto explicado en AC", value=_round_number(ajuste_costo_ac)),
        TableSummaryItem(label="Total usado en dashboard costo", value=_round_number(total_ajuste_costo)),
        TableSummaryItem(label="Saldo costo por revisar", value=_round_number(saldo_dif_costo)),
    ]
    np_summary = [
        TableSummaryItem(label="Total ajuste unidades NP", value=_round_number(ajuste_cant_np)),
        TableSummaryItem(label="Saldo unidades por revisar", value=_round_number(saldo_dif_cant)),
    ]

    return ConciliacionResponse(
        factura=factura,
        nit=nit,
        dashboard=dashboard,
        detalle=_table_from_dataframe(detail_frame),
        ac=_table_from_dataframe(ac_frame, totals=ac_totals, summary=ac_summary),
        np=_table_from_dataframe(np_frame, totals=np_totals, summary=np_summary),
    )


def build_and_cache_reconciliation(factura: str, nit: str) -> ConciliacionResponse | None:
    if not _invoice_exists(factura, nit):
        invalidate_reconciliation_cache(factura, nit)
        return None

    payload = _build_reconciliation_payload(factura, nit)
    _write_cache_file(_cache_file_path(factura, nit), payload)
    return payload


def get_reconciliation(factura: str, nit: str, force_refresh: bool = False) -> ConciliacionResponse | None:
    if not force_refresh:
        cached_payload = load_reconciliation_snapshot(factura, nit)
        if cached_payload is not None:
            return cached_payload

    if not _invoice_exists(factura, nit):
        invalidate_reconciliation_cache(factura, nit)
        return None

    return build_and_cache_reconciliation(factura, nit)
