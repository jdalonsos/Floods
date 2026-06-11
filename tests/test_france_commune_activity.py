from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
SITE_PACKAGES = PROJECT_ROOT / ".venv" / "Lib" / "site-packages"
if str(SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(SITE_PACKAGES))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from france_commune_activity import (  # noqa: E402
    build_month_period,
    filter_records_active_between,
    normalize_commune_name,
    prepare_raw_gaspar_rows,
    resolve_gaspar_current_communes,
)


def make_lookup() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "lau_code": "FR_2B246",
                "lau_code_local": "2B246",
                "lau_name_lau": "La Porta",
                "insee_com": "2B246",
                "commune_name_adminexpress": "La Porta",
                "insee_dep": "2B",
                "insee_reg": "94",
                "adminexpress_population": "180",
                "adminexpress_statut": "Commune simple",
                "nuts3_code": "FRM02",
                "nuts3_name": "Haute-Corse",
                "match_type": "exact",
                "match_method": "exact_code",
                "insee_code_changed_from_lau": "False",
            },
            {
                "lau_code": "FR_01165",
                "lau_code_local": "01165",
                "lau_name_lau": "Francheleins",
                "insee_com": "01165",
                "commune_name_adminexpress": "Francheleins",
                "insee_dep": "01",
                "insee_reg": "84",
                "adminexpress_population": "1500",
                "adminexpress_statut": "Commune simple",
                "nuts3_code": "FRK21",
                "nuts3_name": "Ain",
                "match_type": "exact",
                "match_method": "exact_code",
                "insee_code_changed_from_lau": "False",
            },
            {
                "lau_code": "FR_01330",
                "lau_code_local": "01330",
                "lau_name_lau": "Ruffieu",
                "insee_com": "01187",
                "commune_name_adminexpress": "Haut Valromey",
                "insee_dep": "01",
                "insee_reg": "84",
                "adminexpress_population": "1200",
                "adminexpress_statut": "Commune simple",
                "nuts3_code": "FRK21",
                "nuts3_name": "Ain",
                "match_type": "fallback_spatial",
                "match_method": "spatial_point_within",
                "insee_code_changed_from_lau": "True",
            },
        ]
    )


class FranceCommuneActivityTests(unittest.TestCase):
    def test_normalize_commune_name_strips_accents_and_punctuation(self) -> None:
        self.assertEqual(normalize_commune_name("Saint-Martin-d'Auxy"), "SAINT MARTIN D AUXY")
        self.assertEqual(normalize_commune_name("Bage-Dommartin"), "BAGE DOMMARTIN")

    def test_filter_records_active_between_uses_overlap_logic(self) -> None:
        rows = pd.DataFrame(
            {
                "start": pd.to_datetime(["2020-01-01", "2020-01-10", "2020-02-01"]),
                "end": pd.to_datetime(["2020-01-05", "2020-01-20", "2020-02-03"]),
            }
        )

        january = build_month_period(2020, 1)
        filtered = filter_records_active_between(
            rows,
            start_col="start",
            end_col="end",
            period_start=january.start_date,
            period_end=january.end_date,
        )

        self.assertEqual(len(filtered), 2)

    def test_resolve_gaspar_current_communes_handles_exact_history_and_name_fallbacks(self) -> None:
        gaspar_rows = pd.DataFrame(
            {
                "cod_nat_catnat": ["A", "B", "C", "D"],
                "gaspar_source_cod_commune": ["2B246", "01003", pd.NA, pd.NA],
                "gaspar_source_insee_com": pd.Series(["2B246", "01003", pd.NA, pd.NA], dtype="string"),
                "gaspar_commune_name": ["La Porta", "Amareins", "La Porta", "Ruffieu"],
            }
        )
        historical_updates = pd.DataFrame(
            {
                "old_insee_com": ["01003"],
                "new_insee_com": ["01165"],
            }
        )

        resolved, diagnostics = resolve_gaspar_current_communes(
            gaspar_rows,
            france_lookup=make_lookup(),
            historical_updates=historical_updates,
        )

        methods = resolved["gaspar_commune_match_method"].tolist()
        current_codes = resolved["insee_com"].tolist()

        self.assertEqual(methods[0], "current_code_exact")
        self.assertEqual(current_codes[0], "2B246")

        self.assertEqual(methods[1], "historical_code_update_ready")
        self.assertEqual(current_codes[1], "01165")

        self.assertEqual(methods[2], "current_name_unique_adminexpress")
        self.assertEqual(current_codes[2], "2B246")

        self.assertEqual(methods[3], "current_name_unique_lau")
        self.assertEqual(current_codes[3], "01187")

        self.assertEqual(diagnostics["unresolved_rows"], 0)

    def test_prepare_raw_gaspar_rows_reads_semicolon_csv_and_keeps_full_history(self) -> None:
        raw_csv = """cod_nat_catnat;cod_commune;lib_commune;num_risque_jo;lib_risque_jo;dat_deb;dat_fin
CAT001;01001;Ancienneville;ICB;Inondations et/ou Coulées de Boue;1987-02-11;1987-02-13
CAT002;01002;Waveville;VAG;Chocs Mécaniques liés à l'action des Vagues;1999-12-25;1999-12-27
CAT003;01003;Slideville;GLT;Glissement de Terrain;1988-01-01;1988-01-03
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "catnat_gaspar.csv"
            csv_path.write_text(raw_csv, encoding="utf-8")

            prepared, diagnostics = prepare_raw_gaspar_rows(csv_path)

        self.assertEqual(prepared["cod_nat_catnat"].tolist(), ["CAT001", "CAT002"])
        self.assertEqual(
            prepared["gaspar_event_uid"].tolist(),
            ["CAT001__19870211__19870213", "CAT002__19991225__19991227"],
        )
        self.assertEqual(prepared["gaspar_source_insee_com"].tolist(), ["01001", "01002"])
        self.assertEqual(diagnostics["rows_after_flood_risk_filter"], 2)
        self.assertFalse(diagnostics["optional_date_window_applied"])
        self.assertEqual(diagnostics["canonical_rows_after_dedup"], 2)


if __name__ == "__main__":
    unittest.main()
