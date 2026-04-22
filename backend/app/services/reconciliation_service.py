import json
import re
from decimal import Decimal
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

CACHE_VERSION = "v6"

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

    frame = pd.DataFrame(rows, columns=columns)

    if not frame.empty:
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
        total_row["estado"] = "OK" if abs(total_difference) <= 50 else "DIFERENCIA TOTAL"
        total_row["xml_precio"] = 0
        total_row["erp_precio"] = 0
        total_row["dif_precio"] = 0
        frame.loc[len(frame)] = total_row

    return frame


def _coerce_numeric_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    normalized = frame.copy()
    for column in NUMERIC_COLUMNS:
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    return normalized


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
    frame = _get_comparison_dataframe(factura, nit)
    items_frame = _coerce_numeric_columns(frame[frame["codigo_barras"] != "TOTAL FACTURA"].copy())
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

    ac_frame = items_frame.copy()
    np_cost_adjustment = (
        (items_frame["xml_cant"] - items_frame["erp_cant"])
        * items_frame["erp_precio"].where(items_frame["erp_precio"] > 0, items_frame["xml_precio"])
    ).where(~packaging_mask, 0)
    ac_frame["COSTO_DIF_TOTAL"] = ac_frame["dif_total"] - np_cost_adjustment
    effective_qty = ac_frame["xml_cant"].where(ac_frame["xml_cant"] > 0, ac_frame["erp_cant"]).replace(0, 1)
    ac_frame["DIF_COSTO_UND"] = ac_frame["COSTO_DIF_TOTAL"] / effective_qty
    ac_frame["ORIGEN_AJUSTE"] = packaging_mask.map(
        lambda detected: "EMPAQUE DETECTADO"
        if detected
        else "AJUSTE DE COSTO"
    )
    ac_frame = ac_frame[
        [
            "item_xml",
            "item_erp",
            "descripcion_xml",
            "descripcion_erp",
            "DIF_COSTO_UND",
            "xml_cant",
            "COSTO_DIF_TOTAL",
            "ORIGEN_AJUSTE",
        ]
    ]
    ac_frame.columns = [
        "ITEM_XML",
        "ITEM_ERP",
        "DESCRIPCION_XML",
        "DESCRIPCION_ERP",
        "DIF_COSTO_UND",
        "CANTIDAD_XML",
        "COSTO_DIF_TOTAL",
        "ORIGEN_AJUSTE",
    ]
    ac_frame = ac_frame[abs(ac_frame["COSTO_DIF_TOTAL"]) >= 1]

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
        if abs(dif_valor) > 1 or abs(dif_cant) > 0
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
        alertas_rescate=int((items_frame["alerta_cruce"] == "RESCATE CEROS").sum()),
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
        TableSummaryItem(label="Total ajuste costo AC", value=_round_number(ajuste_costo_ac)),
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
        detalle=_table_from_dataframe(frame),
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
