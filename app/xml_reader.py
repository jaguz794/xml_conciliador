import xml.etree.ElementTree as ET
import logging

NS = {
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'sts': 'dian:gov:co:facturaelectronica:Structures-2-1',
    'xades': 'http://uri.etsi.org/01903/v1.3.2#',
    'ds': 'http://www.w3.org/2000/09/xmldsig#'
}

def obtener_texto(nodo, xpath):
    try:
        elemento = nodo.find(xpath, NS)
        return elemento.text.strip() if elemento is not None and elemento.text else None
    except Exception:
        return None

def extraer_impuestos(linea_nodo):
    iva_total = 0.0
    icui_total = 0.0
    for tax_total in linea_nodo.findall('.//cac:TaxTotal', NS):
        try:
            monto = float(tax_total.find('cbc:TaxAmount', NS).text)
            tax_scheme = tax_total.find('.//cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme', NS)
            if tax_scheme is not None:
                tax_id = obtener_texto(tax_scheme, 'cbc:ID')
                tax_name = obtener_texto(tax_scheme, 'cbc:Name')
                tax_id = tax_id if tax_id else ""
                tax_name = tax_name if tax_name else ""
                
                if tax_id == '01' or 'IVA' in tax_name.upper():
                    iva_total += monto
                elif tax_id in ['04', '35', 'ZA'] or 'ICUI' in tax_name.upper() or 'INC' in tax_name.upper():
                    icui_total += monto
        except Exception:
            continue
    return iva_total, icui_total

def leer_xml(ruta_xml):
    factura = None
    nit = None
    detalle = []

    try:
        tree = ET.parse(ruta_xml)
        root = tree.getroot()

        # Manejo de AttachedDocument
        if 'AttachedDocument' in root.tag:
            cdata_node = root.find('.//cac:Attachment/cac:ExternalReference/cbc:Description', NS)
            if cdata_node is not None and cdata_node.text:
                root = ET.fromstring(cdata_node.text.strip())
            else:
                return None, None, []

        factura = obtener_texto(root, 'cbc:ID')
        nit = obtener_texto(root, './/cac:AccountingSupplierParty//cac:Party//cac:PartyTaxScheme//cbc:CompanyID')
        if not nit:
            nit = obtener_texto(root, './/cac:AccountingSupplierParty//cbc:CompanyID')

        if not factura:
            return None, None, []

        # Recorrer lineas
        items = root.findall('.//cac:InvoiceLine', NS)
        
        for item in items:
            # --- CORRECCION EXTRACCION ITEM_XML ---
            # Intentamos buscar el codigo interno del vendedor
            # Ruta: InvoiceLine -> Item -> SellersItemIdentification -> ID
            item_xml = obtener_texto(item, 'cac:Item/cac:SellersItemIdentification/cbc:ID')
            
            # Codigo de barras (EAN)
            codigo_barras = obtener_texto(item, 'cac:Item/cac:StandardItemIdentification/cbc:ID')
            
            # Si SellersItemIdentification falla, intentamos usar el Standard como item_xml tambien
            if not item_xml:
                 item_xml = codigo_barras
            
            # Si no hay codigo de barras, usamos el item_xml como backup para el cruce
            if not codigo_barras:
                 codigo_barras = item_xml
            
            descripcion = obtener_texto(item, 'cac:Item/cbc:Description')

            try: cantidad = float(item.find('cbc:InvoicedQuantity', NS).text)
            except: cantidad = 0.0

            try: precio = float(item.find('.//cac:Price/cbc:PriceAmount', NS).text)
            except: precio = 0.0

            try: total_linea = float(item.find('cbc:LineExtensionAmount', NS).text)
            except: total_linea = 0.0

            imp_netos, impoconsumo = extraer_impuestos(item)

            detalle.append({
                "factura": factura,
                "nit": nit,
                "item_xml": item_xml, 
                "codigo_barras": codigo_barras,
                "descripcion": descripcion,
                "cantidad": cantidad,
                "precio": precio,
                "imp_netos": imp_netos,
                "impoconsumo": impoconsumo,
                "descuento": 0,
                "total": total_linea
            })

        return factura, nit, detalle

    except Exception as e:
        logging.error(f"Error procesando XML {ruta_xml}: {e}")
        return None, None, []