import pandas as pd
import logging
import warnings
from db import get_connection

# Ignorar advertencias de compatibilidad de Pandas
warnings.filterwarnings('ignore', category=UserWarning, module='pandas')

def obtener_diferencias(factura, nit):
    logging.info(f"Generando cruce (Filtro EA + Multi-Barras + Rescate Ceros + Precio Real) para Factura: {factura} NIT: {nit}")

    conn = get_connection()
    if not conn:
        logging.error("No se pudo conectar a la base de datos en comparacion.py")
        return None

    try:
        sql = """
        WITH xml_base AS (
            SELECT 
                x.codigo_barras,
                x.item_xml,
                x.descripcion,
                x.cantidad,
                
                -- ¡LA MAGIA AQUÍ! Calculamos el precio real unitario (Total / Cantidad) para absorber descuentos
                COALESCE(ROUND(x.total / NULLIF(x.cantidad, 0)), 0) AS precio_unitario,
                
                x.imp_netos,
                x.impoconsumo,
                x.total,
                x.numero_factura,
                x.nit_proveedor,
                
                -- ==========================================
                -- FASE 1: BÚSQUEDA EXACTA (Súper rápida y segura)
                -- ==========================================
                (SELECT TRIM(h.item_erp) FROM homologacion_items h 
                 WHERE h.nit_prov = x.nit_proveedor AND TRIM(h.item_prov) = TRIM(x.item_xml) AND x.item_xml <> '' LIMIT 1) AS m_hom_prov_exacto,
                
                (SELECT TRIM(h.item_erp) FROM homologacion_items h 
                 WHERE h.nit_prov = x.nit_proveedor AND TRIM(h.cod_barras) = TRIM(x.codigo_barras) AND x.codigo_barras <> '' LIMIT 1) AS m_hom_barras_exacto,
                
                (SELECT MAX(TRIM(cb.id_items)) FROM cod_barras cb 
                 WHERE TRIM(cb.id_codbar) = TRIM(x.codigo_barras) AND x.codigo_barras <> '') AS m_multi_barras_exacto,
                
                (SELECT MAX(TRIM(i.id_item)) FROM items i 
                 WHERE TRIM(i.id_codbar) = TRIM(x.codigo_barras) AND x.codigo_barras <> '') AS m_items_barras_exacto,

                -- ==========================================
                -- FASE 2: PLAN DE RESCATE (Ignorando ceros a la izquierda)
                -- ==========================================
                (SELECT TRIM(h.item_erp) FROM homologacion_items h 
                 WHERE h.nit_prov = x.nit_proveedor 
                 AND LTRIM(TRIM(h.item_prov), '0') = LTRIM(TRIM(x.item_xml), '0') AND x.item_xml <> '' LIMIT 1) AS m_hom_prov_rescate,
                 
                (SELECT TRIM(h.item_erp) FROM homologacion_items h 
                 WHERE h.nit_prov = x.nit_proveedor 
                 AND LTRIM(TRIM(h.cod_barras), '0') = LTRIM(TRIM(x.codigo_barras), '0') AND x.codigo_barras <> '' LIMIT 1) AS m_hom_barras_rescate,
                 
                (SELECT MAX(TRIM(cb.id_items)) FROM cod_barras cb 
                 WHERE LTRIM(TRIM(cb.id_codbar), '0') = LTRIM(TRIM(x.codigo_barras), '0') AND x.codigo_barras <> '') AS m_multi_barras_rescate,
                 
                (SELECT MAX(TRIM(i.id_item)) FROM items i 
                 WHERE LTRIM(TRIM(i.id_codbar), '0') = LTRIM(TRIM(x.codigo_barras), '0') AND x.codigo_barras <> '') AS m_items_barras_rescate

            FROM factura_xml_detalle x
            WHERE x.numero_factura = %s
            AND x.nit_proveedor = %s
        ),
        
        xml_data AS (
            SELECT 
                *,
                -- Escoge el primer método que haya funcionado (Priorizando los exactos)
                COALESCE(
                    m_hom_prov_exacto, m_hom_barras_exacto, m_multi_barras_exacto, m_items_barras_exacto,
                    m_hom_prov_rescate, m_hom_barras_rescate, m_multi_barras_rescate, m_items_barras_rescate
                ) AS item_erp_resuelto,
                
                -- Crea la etiqueta visual si tuvo que usar algún plan de rescate
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
                
                SUM(round(COALESCE(mov.cantidad_1, 0))) as cantidad,
                
                COALESCE(
                    round(
                        SUM(COALESCE(mov.vlr_bruto, 0)) / NULLIF(SUM(COALESCE(mov.cantidad_1, 0)), 0)
                    ), 0
                ) as precio_uni,
                
                SUM(round(COALESCE(mov.vlr_iva, 0))) as imp_netos,
                SUM(round(COALESCE(mov.vlr_impo, 0))) as impoconsumo,
                SUM(round(COALESCE(mov.vlr_bruto, 0))) as tot_compra
            
            FROM cmmovimiento_inventario mov
            INNER JOIN items i 
                ON mov.id_item = i.id_item
            
            WHERE mov.id_terc = %s 
            -- FILTRO EXCLUSIVO PARA ENTRADAS DE ALMACÉN
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
            -- Cruce final blindado a espacios y ceros a la izquierda
            ON LTRIM(TRIM(CAST(x.item_erp_resuelto AS VARCHAR)), '0') = LTRIM(TRIM(CAST(e.item_erp_original AS VARCHAR)), '0')

        ORDER BY estado DESC, codigo_barras ASC;
        """
        
       # Parámetros (orden exacto de Python a PostgreSQL)
        df = pd.read_sql(sql, conn, params=(factura, nit, nit, factura))
        
        # ==========================================
        # NUEVO: AGREGAR FILA DE TOTALES GLOBALES
        # ==========================================
        if not df.empty:
            # Calculamos la suma global para saber si la factura cuadrada en su totalidad
            suma_xml = df['xml_total'].sum()
            suma_erp = df['erp_total'].sum()
            diferencia_global = suma_xml - suma_erp
            
            # Si el descuadre de toda la factura supera los 50 pesos, alertamos
            estado_global = 'OK' if abs(diferencia_global) <= 50 else 'DIFERENCIA TOTAL'

            # Creamos un diccionario con celdas vacías para la nueva fila
            fila_totales = {col: '' for col in df.columns}
            
            # Llenamos los textos de la fila final
            fila_totales['codigo_barras'] = 'TOTAL FACTURA'
            fila_totales['descripcion_xml'] = '>>> SUMA GLOBAL DE LA FACTURA <<<'
            fila_totales['estado'] = estado_global
            
            # Sumamos las columnas matemáticas (Cantidades, IVA, ICUI, Totales)
            columnas_a_sumar = [
                'xml_cant', 'erp_cant', 'dif_cant', 
                'xml_iva', 'erp_iva', 'dif_iva', 
                'xml_icui', 'erp_icui', 'dif_icui', 
                'xml_total', 'erp_total', 'dif_total'
            ]
            
            for col in columnas_a_sumar:
                if col in df.columns:
                    fila_totales[col] = df[col].sum()
            
            # Los precios unitarios no se suman (matemáticamente no tiene sentido sumar precios unitarios)
            fila_totales['xml_precio'] = 0
            fila_totales['erp_precio'] = 0
            fila_totales['dif_precio'] = 0

            # Insertamos la fila al final del DataFrame
            df.loc[len(df)] = fila_totales
        # ==========================================
        
        logging.info(f"Cruce detallado finalizado. Filas procesadas: {len(df)}")
        return df

    except Exception as e:
        logging.error(f"Error en comparacion SQL: {e}")
        return None 
    finally:
        if conn:
            conn.close()