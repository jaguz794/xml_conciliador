import unittest

import pandas as pd

from backend.app.services.reconciliation_service import (
    COMPARISON_SQL,
    _apply_xml_package_adjustment,
    _build_ac_explanation_frame,
    _build_erp_invoice_lookup,
    _infer_package_factor_from_matched_rows,
    _merge_packaging_rows,
    _recalculate_comparison_columns,
)


class ReconciliationPackagingTests(unittest.TestCase):
    def test_builds_normalized_lookup_for_erp_invoice_reference(self) -> None:
        self.assertEqual(
            _build_erp_invoice_lookup("06 145387"),
            ("06145387", "06145387", "6145387"),
        )
        self.assertEqual(
            _build_erp_invoice_lookup("06145387"),
            ("06145387", "06145387", "6145387"),
        )

    def test_comparison_sql_checks_provider_and_fp_reference(self) -> None:
        self.assertIn("COALESCE(NULLIF(mov.id_terc_prov, ''), mov.id_terc) = %s", COMPARISON_SQL)
        self.assertIn("REPLACE(mov.tipo_fp, ' ', '') || REPLACE(mov.nro_fp, ' ', '') = %s", COMPARISON_SQL)

    def test_extracts_explicit_package_factor_from_xml_description(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "codigo_barras": "7702007039696",
                    "item_xml": "7702007039696",
                    "item_erp": None,
                    "descripcion_xml": "GLINA. JUMBO FLOW 12PLEX12UNX48G",
                    "descripcion_erp": None,
                    "estado": "FALTA EN ERP",
                    "alerta_cruce": "",
                    "xml_cant": 1.0,
                    "erp_cant": 0.0,
                    "dif_cant": 1.0,
                    "xml_precio": 12000.0,
                    "erp_precio": 0.0,
                    "dif_precio": 12000.0,
                    "xml_iva": 0.0,
                    "erp_iva": 0.0,
                    "dif_iva": 0.0,
                    "xml_icui": 0.0,
                    "erp_icui": 0.0,
                    "dif_icui": 0.0,
                    "xml_total": 12000.0,
                    "erp_total": 0.0,
                    "dif_total": 12000.0,
                }
            ]
        )

        adjusted = _apply_xml_package_adjustment(frame)

        self.assertEqual(int(adjusted.loc[0, "xml_factor_empaque"]), 12)
        self.assertEqual(float(adjusted.loc[0, "xml_cant_original"]), 1.0)
        self.assertEqual(float(adjusted.loc[0, "xml_cant"]), 1.0)
        self.assertEqual(str(adjusted.loc[0, "alerta_cruce"]), "")

    def test_inferrs_factor_when_total_matches_even_without_un_token(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "codigo_barras": "7702007030075",
                    "item_xml": "7702007030075",
                    "item_erp": "022301",
                    "descripcion_xml": "REPOST. NALCHOC CRE. CHANTILLY 12PLEX80G",
                    "descripcion_erp": "CREMA CORONA*80g CHANTILLY INST UND",
                    "estado": "DIFERENCIA CANTIDAD",
                    "alerta_cruce": "",
                    "xml_cant": 1.0,
                    "erp_cant": 12.0,
                    "dif_cant": -11.0,
                    "xml_precio": 58160.0,
                    "erp_precio": 4846.67,
                    "dif_precio": 53313.33,
                    "xml_iva": 0.0,
                    "erp_iva": 0.0,
                    "dif_iva": 0.0,
                    "xml_icui": 0.0,
                    "erp_icui": 0.0,
                    "dif_icui": 0.0,
                    "xml_total": 58160.0,
                    "erp_total": 58160.0,
                    "dif_total": 0.0,
                    "xml_cant_original": 1.0,
                    "xml_factor_empaque": 1,
                }
            ]
        )

        adjusted = _infer_package_factor_from_matched_rows(frame)
        adjusted = _recalculate_comparison_columns(adjusted)

        self.assertEqual(int(adjusted.loc[0, "xml_factor_empaque"]), 12)
        self.assertEqual(float(adjusted.loc[0, "xml_cant"]), 12.0)
        self.assertAlmostEqual(float(adjusted.loc[0, "dif_cant"]), 0.0, places=2)
        self.assertEqual(str(adjusted.loc[0, "estado"]), "OK")
        self.assertIn("CRUCE EMPAQUE", str(adjusted.loc[0, "alerta_cruce"]))

    def test_does_not_infer_factor_for_incompatible_matched_descriptions(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "codigo_barras": "7702000000001",
                    "item_xml": "23349",
                    "item_erp": "048611",
                    "descripcion_xml": "UVA POSTOBON 1.500 ML PET X 12 MOD",
                    "descripcion_erp": "GAS POSTOBON*400ml TORONJA PET",
                    "estado": "DIFERENCIA CANTIDAD",
                    "alerta_cruce": "",
                    "xml_cant": 1.0,
                    "erp_cant": 12.0,
                    "dif_cant": -11.0,
                    "xml_precio": 42000.0,
                    "erp_precio": 3500.0,
                    "dif_precio": 38500.0,
                    "xml_iva": 0.0,
                    "erp_iva": 0.0,
                    "dif_iva": 0.0,
                    "xml_icui": 0.0,
                    "erp_icui": 0.0,
                    "dif_icui": 0.0,
                    "xml_total": 42000.0,
                    "erp_total": 42000.0,
                    "dif_total": 0.0,
                    "xml_cant_original": 1.0,
                    "xml_factor_empaque": 1,
                }
            ]
        )

        adjusted = _infer_package_factor_from_matched_rows(frame)
        adjusted = _recalculate_comparison_columns(adjusted)

        self.assertEqual(int(adjusted.loc[0, "xml_factor_empaque"]), 1)
        self.assertEqual(float(adjusted.loc[0, "xml_cant"]), 1.0)
        self.assertEqual(str(adjusted.loc[0, "estado"]), "DIFERENCIA CANTIDAD")
        self.assertEqual(str(adjusted.loc[0, "alerta_cruce"]), "")

    def test_merges_split_xml_and_erp_rows_for_packaging_case(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "codigo_barras": "7702007082036",
                    "item_xml": "7702007082036",
                    "item_erp": None,
                    "descripcion_xml": "GLINA. TIKYS GOLOCHIPS 6PLEGX24UNX20GR",
                    "descripcion_erp": None,
                    "estado": "FALTA EN ERP",
                    "alerta_cruce": "",
                    "xml_cant": 1.0,
                    "erp_cant": 0.0,
                    "dif_cant": 1.0,
                    "xml_precio": 26889.0,
                    "erp_precio": 0.0,
                    "dif_precio": 26889.0,
                    "xml_iva": 0.0,
                    "erp_iva": 0.0,
                    "dif_iva": 0.0,
                    "xml_icui": 0.0,
                    "erp_icui": 0.0,
                    "dif_icui": 0.0,
                    "xml_total": 26889.0,
                    "erp_total": 0.0,
                    "dif_total": 26889.0,
                },
                {
                    "codigo_barras": "7702007082035",
                    "item_xml": None,
                    "item_erp": "047457",
                    "descripcion_xml": None,
                    "descripcion_erp": "GOLOSINA TIKIS*20g GOLOCHIPS",
                    "estado": "FALTA EN XML",
                    "alerta_cruce": "",
                    "xml_cant": 0.0,
                    "erp_cant": 24.0,
                    "dif_cant": -24.0,
                    "xml_precio": 0.0,
                    "erp_precio": 1120.375,
                    "dif_precio": -1120.375,
                    "xml_iva": 0.0,
                    "erp_iva": 0.0,
                    "dif_iva": 0.0,
                    "xml_icui": 0.0,
                    "erp_icui": 0.0,
                    "dif_icui": 0.0,
                    "xml_total": 0.0,
                    "erp_total": 26889.0,
                    "dif_total": -26889.0,
                },
            ]
        )

        adjusted = _apply_xml_package_adjustment(frame)
        merged = _merge_packaging_rows(adjusted)
        merged = _recalculate_comparison_columns(merged)

        self.assertEqual(len(merged), 1)
        self.assertEqual(str(merged.loc[0, "item_erp"]), "047457")
        self.assertEqual(int(merged.loc[0, "xml_factor_empaque"]), 24)
        self.assertEqual(float(merged.loc[0, "xml_cant"]), 24.0)
        self.assertEqual(float(merged.loc[0, "erp_cant"]), 24.0)
        self.assertEqual(str(merged.loc[0, "estado"]), "OK")
        self.assertIn("CRUCE EMPAQUE", str(merged.loc[0, "alerta_cruce"]))

    def test_does_not_merge_split_rows_for_incompatible_products(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "codigo_barras": "7702000000001",
                    "item_xml": "23349",
                    "item_erp": None,
                    "descripcion_xml": "UVA POSTOBON 1.500 ML PET X 12 MOD",
                    "descripcion_erp": None,
                    "estado": "FALTA EN ERP",
                    "alerta_cruce": "",
                    "xml_cant": 1.0,
                    "erp_cant": 0.0,
                    "dif_cant": 1.0,
                    "xml_precio": 42000.0,
                    "erp_precio": 0.0,
                    "dif_precio": 42000.0,
                    "xml_iva": 0.0,
                    "erp_iva": 0.0,
                    "dif_iva": 0.0,
                    "xml_icui": 0.0,
                    "erp_icui": 0.0,
                    "dif_icui": 0.0,
                    "xml_total": 42000.0,
                    "erp_total": 0.0,
                    "dif_total": 42000.0,
                },
                {
                    "codigo_barras": "7702000000002",
                    "item_xml": None,
                    "item_erp": "048611",
                    "descripcion_xml": None,
                    "descripcion_erp": "GAS POSTOBON*400ml TORONJA PET",
                    "estado": "FALTA EN XML",
                    "alerta_cruce": "",
                    "xml_cant": 0.0,
                    "erp_cant": 12.0,
                    "dif_cant": -12.0,
                    "xml_precio": 0.0,
                    "erp_precio": 3500.0,
                    "dif_precio": -3500.0,
                    "xml_iva": 0.0,
                    "erp_iva": 0.0,
                    "dif_iva": 0.0,
                    "xml_icui": 0.0,
                    "erp_icui": 0.0,
                    "dif_icui": 0.0,
                    "xml_total": 0.0,
                    "erp_total": 42000.0,
                    "dif_total": -42000.0,
                },
            ]
        )

        adjusted = _apply_xml_package_adjustment(frame)
        merged = _merge_packaging_rows(adjusted)
        merged = _recalculate_comparison_columns(merged)

        self.assertEqual(len(merged), 2)
        self.assertEqual(str(merged.loc[0, "estado"]), "FALTA EN ERP")
        self.assertEqual(str(merged.loc[1, "estado"]), "FALTA EN XML")
        self.assertNotIn("CRUCE EMPAQUE", str(merged.loc[0, "alerta_cruce"]))
        self.assertNotIn("CRUCE EMPAQUE", str(merged.loc[1, "alerta_cruce"]))

    def test_does_not_pair_ac_explanation_rows_for_incompatible_products(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "item_xml": "23349",
                    "item_erp": None,
                    "descripcion_xml": "UVA POSTOBON 1.500 ML PET X 12 MOD",
                    "descripcion_erp": None,
                    "alerta_cruce": "",
                    "xml_cant": 12.0,
                    "erp_cant": 0.0,
                    "xml_total": 42000.0,
                    "erp_total": 0.0,
                },
                {
                    "item_xml": None,
                    "item_erp": "048611",
                    "descripcion_xml": None,
                    "descripcion_erp": "GAS POSTOBON*400ml TORONJA PET",
                    "alerta_cruce": "",
                    "xml_cant": 0.0,
                    "erp_cant": 12.0,
                    "xml_total": 0.0,
                    "erp_total": 42000.0,
                },
            ]
        )

        ac_frame = _build_ac_explanation_frame(frame)

        self.assertEqual(len(ac_frame), 2)
        self.assertEqual(str(ac_frame.loc[0, "ORIGEN_AJUSTE"]), "SOLO XML")
        self.assertEqual(str(ac_frame.loc[1, "ORIGEN_AJUSTE"]), "SOLO ERP")


if __name__ == "__main__":
    unittest.main()
