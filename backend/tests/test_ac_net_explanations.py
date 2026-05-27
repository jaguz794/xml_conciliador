import unittest

import pandas as pd

from backend.app.services.reconciliation_service import _build_ac_explanation_frame


class AcNetExplanationTests(unittest.TestCase):
    def test_hides_one_sided_pairs_that_cancel_out_exactly(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "item_xml": None,
                    "item_erp": "025119",
                    "descripcion_xml": None,
                    "descripcion_erp": "CHOCOLATI JUMBO FLOW*48g",
                    "xml_cant": 0.0,
                    "erp_cant": 12.0,
                    "xml_total": 0.0,
                    "erp_total": 30655.0,
                    "dif_total": -30655.0,
                },
                {
                    "item_xml": "7702007039696",
                    "item_erp": None,
                    "descripcion_xml": "GLINA. JUMBO FLOW 12PLEX12UNX48G",
                    "descripcion_erp": None,
                    "xml_cant": 1.0,
                    "erp_cant": 0.0,
                    "xml_total": 30655.0,
                    "erp_total": 0.0,
                    "dif_total": 30655.0,
                },
                {
                    "item_xml": "7702007056723",
                    "item_erp": "023753",
                    "descripcion_xml": "PREMEZ. CORONA TORTA CHOCOL 12BOLX450G",
                    "descripcion_erp": "TORTA CORONA*450g CHOCOLATE",
                    "xml_cant": 2.0,
                    "erp_cant": 2.0,
                    "xml_total": 20256.0,
                    "erp_total": 20252.0,
                    "dif_total": 4.0,
                },
            ]
        )

        ac_frame = _build_ac_explanation_frame(frame)

        self.assertEqual(len(ac_frame), 1)
        self.assertEqual(float(ac_frame.iloc[0]["COSTO_DIF_TOTAL"]), 4.0)
        self.assertEqual(str(ac_frame.iloc[0]["ORIGEN_AJUSTE"]), "DIFERENCIA NETA ERP/XML")
        self.assertEqual(float(ac_frame["COSTO_DIF_TOTAL"].sum()), float(frame["dif_total"].sum()))

    def test_pairs_xml_and_erp_only_rows_into_their_net_difference(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "item_xml": None,
                    "item_erp": "047457",
                    "descripcion_xml": None,
                    "descripcion_erp": "GOLOSINA TIKIS*20g GOLOCHIPS",
                    "xml_cant": 0.0,
                    "erp_cant": 24.0,
                    "xml_total": 0.0,
                    "erp_total": 26895.0,
                    "dif_total": -26895.0,
                },
                {
                    "item_xml": "7702007082036",
                    "item_erp": None,
                    "descripcion_xml": "GLINA. TIKYS GOLOCHIPS 6PLEGX24UNX20GR",
                    "descripcion_erp": None,
                    "xml_cant": 1.0,
                    "erp_cant": 0.0,
                    "xml_total": 26889.0,
                    "erp_total": 0.0,
                    "dif_total": 26889.0,
                },
                {
                    "item_xml": "7702007213874",
                    "item_erp": "019366",
                    "descripcion_xml": "REPOST. CORONA CHIPS CHTE 24BOLX250G",
                    "descripcion_erp": "COBERTURA CORONA*250g CHIPS CHOCOLATE",
                    "xml_cant": 8.0,
                    "erp_cant": 8.0,
                    "xml_total": 61936.0,
                    "erp_total": 61934.0,
                    "dif_total": 2.0,
                },
            ]
        )

        ac_frame = _build_ac_explanation_frame(frame)

        self.assertEqual(len(ac_frame), 2)
        self.assertEqual(float(ac_frame["COSTO_DIF_TOTAL"].sum()), float(frame["dif_total"].sum()))

        paired_row = ac_frame[ac_frame["ORIGEN_AJUSTE"] == "CRUCE NETO ERP/XML"].iloc[0]
        self.assertEqual(float(paired_row["COSTO_DIF_TOTAL"]), -6.0)
        self.assertEqual(float(paired_row["CANTIDAD_ERP"]), 24.0)
        self.assertEqual(float(paired_row["DIF_COSTO_UND"]), -0.25)

    def test_keeps_packaging_context_in_ac_origin(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "item_xml": "7702007082036",
                    "item_erp": "047457",
                    "descripcion_xml": "GLINA. TIKYS GOLOCHIPS 6PLEGX24UNX20GR",
                    "descripcion_erp": "GOLOSINA TIKIS*20g GOLOCHIPS",
                    "alerta_cruce": "CRUCE EMPAQUE",
                    "xml_cant": 24.0,
                    "erp_cant": 24.0,
                    "xml_total": 26889.0,
                    "erp_total": 26895.0,
                    "dif_total": -6.0,
                }
            ]
        )

        ac_frame = _build_ac_explanation_frame(frame)

        self.assertEqual(len(ac_frame), 1)
        self.assertEqual(
            str(ac_frame.iloc[0]["ORIGEN_AJUSTE"]),
            "DIFERENCIA NETA ERP/XML | CRUCE EMPAQUE",
        )


if __name__ == "__main__":
    unittest.main()
