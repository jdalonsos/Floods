from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
SITE_PACKAGES = PROJECT_ROOT / ".venv" / "Lib" / "site-packages"
if str(SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(SITE_PACKAGES))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from check_points_against_gaspar_floods import (  # noqa: E402
    derive_gaspar_only_output_path,
    ensure_required_path,
    resolve_output_path,
)


class CheckPointsAgainstGasparFloodsTests(unittest.TestCase):
    def test_derive_gaspar_only_output_path_uses_points_workbook_stem(self) -> None:
        points_file = Path("data/processed/T20_Anonymised.xlsx")

        result = derive_gaspar_only_output_path(points_file)

        self.assertEqual(result, Path("data/processed/T20_Anonymised_gaspar_check.xlsx"))

    def test_resolve_output_path_prefers_explicit_argument(self) -> None:
        points_file = Path("data/processed/T20_Anonymised.xlsx")
        explicit_output = "data/processed/custom_gaspar_output.xlsx"

        result = resolve_output_path(points_file, explicit_output)

        self.assertEqual(result, Path(explicit_output))

    def test_ensure_required_path_raises_clear_error_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_path = Path(tmp_dir) / "missing.xlsx"

            with self.assertRaises(FileNotFoundError) as context:
                ensure_required_path(missing_path, "Gaspar workbook")

        self.assertIn("Missing required Gaspar workbook", str(context.exception))


if __name__ == "__main__":
    unittest.main()
