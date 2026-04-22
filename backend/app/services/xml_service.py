import xml.etree.ElementTree as ET

NS = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "sts": "dian:gov:co:facturaelectronica:Structures-2-1",
    "xades": "http://uri.etsi.org/01903/v1.3.2#",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
}


def _get_text(node: ET.Element, xpath: str) -> str | None:
    try:
        element = node.find(xpath, NS)
        return element.text.strip() if element is not None and element.text else None
    except Exception:
        return None


def _extract_taxes(line_node: ET.Element) -> tuple[float, float]:
    vat_total = 0.0
    icui_total = 0.0

    for tax_total in line_node.findall(".//cac:TaxTotal", NS):
        try:
            amount_node = tax_total.find("cbc:TaxAmount", NS)
            amount = float(amount_node.text) if amount_node is not None else 0.0
            tax_scheme = tax_total.find(
                ".//cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme",
                NS,
            )
            if tax_scheme is None:
                continue

            tax_id = (_get_text(tax_scheme, "cbc:ID") or "").upper()
            tax_name = (_get_text(tax_scheme, "cbc:Name") or "").upper()

            if tax_id == "01" or "IVA" in tax_name:
                vat_total += amount
            elif tax_id in {"04", "35", "ZA"} or "ICUI" in tax_name or "INC" in tax_name:
                icui_total += amount
        except Exception:
            continue

    return vat_total, icui_total


def parse_invoice_xml(content: bytes) -> tuple[str | None, str | None, list[dict]]:
    factura = None
    nit = None
    detail: list[dict] = []

    try:
        root = ET.fromstring(content)

        if "AttachedDocument" in root.tag:
            cdata_node = root.find(
                ".//cac:Attachment/cac:ExternalReference/cbc:Description",
                NS,
            )
            if cdata_node is not None and cdata_node.text:
                root = ET.fromstring(cdata_node.text.strip())
            else:
                return None, None, []

        factura = _get_text(root, "cbc:ID")
        nit = _get_text(
            root,
            ".//cac:AccountingSupplierParty//cac:Party//cac:PartyTaxScheme//cbc:CompanyID",
        )
        if not nit:
            nit = _get_text(root, ".//cac:AccountingSupplierParty//cbc:CompanyID")

        if not factura or not nit:
            return None, None, []

        for item in root.findall(".//cac:InvoiceLine", NS):
            item_xml = _get_text(item, "cac:Item/cac:SellersItemIdentification/cbc:ID")
            barcode = _get_text(item, "cac:Item/cac:StandardItemIdentification/cbc:ID")

            if not item_xml:
                item_xml = barcode
            if not barcode:
                barcode = item_xml

            description = _get_text(item, "cac:Item/cbc:Description")

            try:
                quantity_node = item.find("cbc:InvoicedQuantity", NS)
                quantity = float(quantity_node.text) if quantity_node is not None else 0.0
            except Exception:
                quantity = 0.0

            try:
                price_node = item.find(".//cac:Price/cbc:PriceAmount", NS)
                price = float(price_node.text) if price_node is not None else 0.0
            except Exception:
                price = 0.0

            try:
                total_node = item.find("cbc:LineExtensionAmount", NS)
                total = float(total_node.text) if total_node is not None else 0.0
            except Exception:
                total = 0.0

            vat_total, icui_total = _extract_taxes(item)

            detail.append(
                {
                    "factura": factura,
                    "nit": nit,
                    "item_xml": item_xml,
                    "codigo_barras": barcode,
                    "descripcion": description,
                    "cantidad": quantity,
                    "precio": price,
                    "imp_netos": vat_total,
                    "impoconsumo": icui_total,
                    "descuento": 0,
                    "total": total,
                }
            )

        return factura, nit, detail

    except Exception:
        return None, None, []
