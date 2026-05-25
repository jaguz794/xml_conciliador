import unittest

import pandas as pd

from backend.app.services.reconciliation_service import _append_total_row


class TotalFacturaStatusTests(unittest.TestCase):
    def test_total_row_marks_difference_when_gap_exceeds_one_peso(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "codigo_barras": "7702007034257",
                    "item_xml": "7702007034257",
                    "item_erp": "022771",
                    "descripcion_xml": "GLINA. JET CRUJI 12PLEX24UNDX11GR",
                    "descripcion_erp": "CHOCOLATI JET*11g CRUJI",
                    "estado": "DIFERENCIA TOTAL",
                    "alerta_cruce": "",
                    "xml_cant": 24.0,
                    "erp_cant": 24.0,
                    "dif_cant": 0.0,
                    "xml_precio": 683.0,
                    "erp_precio": 683.0,
                    "dif_precio": 0.0,
                    "xml_iva": 3115.0,
                    "erp_iva": 3115.0,
                    "dif_iva": 0.0,
                    "xml_icui": 0.0,
                    "erp_icui": 0.0,
                    "dif_icui": 0.0,
                    "xml_total": 16397.0,
                    "erp_total": 16393.0,
                    "dif_total": 4.0,
                }
            ]
        )

        with_total = _append_total_row(frame)
        total_row = with_total.iloc[-1]

        self.assertEqual(str(total_row["codigo_barras"]), "TOTAL FACTURA")
        self.assertEqual(float(total_row["dif_total"]), 4.0)
        self.assertEqual(str(total_row["estado"]), "DIFERENCIA TOTAL")


if __name__ == "__main__":
    unittest.main()
