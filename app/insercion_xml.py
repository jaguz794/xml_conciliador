from db import get_connection

def insertar_detalle(detalle):
    conn = get_connection()
    cur = conn.cursor()

    # Se agrego la columna item_xml al insert
    sql = """
    INSERT INTO factura_xml_detalle
    (numero_factura, nit_proveedor, item_xml, codigo_barras, descripcion,
     cantidad, precio_unitario, imp_netos, impoconsumo, descuento, total)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """

    for d in detalle:
        cur.execute(sql, (
            d["factura"], d["nit"], 
            d.get("item_xml"),
            d["codigo_barras"], d["descripcion"],
            d["cantidad"], d["precio"], d["imp_netos"],
            d["impoconsumo"], d["descuento"], d["total"]
        ))

    conn.commit()
    cur.close()
    conn.close()

def limpiar_factura(factura, nit):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM factura_xml_detalle
        WHERE numero_factura = %s
        AND nit_proveedor = %s
    """, (factura, nit))
    conn.commit()
    cur.close()
    conn.close()