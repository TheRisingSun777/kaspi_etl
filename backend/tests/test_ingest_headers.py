import unittest
from unittest import mock

import pandas as pd

from backend.ingest import xlsx_offers_loader, xlsx_loaders


class TestDeliveryHeaderNormalization(unittest.TestCase):
    def test_percent_header_alias_recognized(self) -> None:
        alias = "PlatformDLVPct_innercity"
        columns = {xlsx_loaders._normalize_header(alias): alias}
        resolved = xlsx_loaders._find_column(
            columns, xlsx_loaders.DELIVERY_HEADER_MAP["fee_city_pct"]
        )
        self.assertEqual(resolved, alias)

    def test_validate_percent_row_normalizes(self) -> None:
        payload = {
            "price_min": "100",
            "price_max": "150",
            "weight_min_kg": "1",
            "weight_max_kg": "2",
            "fee_city_pct": "25",
            "fee_country_pct": 0.5,
        }
        result = xlsx_loaders._validate_delivery_row(payload, 0)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["fee_city_pct"], 0.25)
        self.assertAlmostEqual(result["fee_country_pct"], 0.5)
        self.assertIsNone(result["fee_city_kzt"])
        self.assertIsNone(result["fee_country_kzt"])


class TestOfferStoreMapping(unittest.TestCase):
    def _fake_config(self):
        class Account:
            def __init__(self, name: str, account_id: str) -> None:
                self.name = name
                self.account_id = account_id

        class Kaspi:
            def __init__(self) -> None:
                self.accounts = [
                    Account("UNIVERSAL", "30141222"),
                    Account("ONLYFIT", "30290083"),
                ]

        fake_config = mock.Mock()
        fake_config.kaspi = Kaspi()
        return fake_config

    def test_store_name_maps_to_account(self) -> None:
        fake_config = self._fake_config()

        with mock.patch("backend.ingest.xlsx_offers_loader.load_config", return_value=fake_config):
            mapping = xlsx_offers_loader.load_store_name_to_id_map()

        self.assertEqual(mapping["universal"], "30141222")

        account_id = xlsx_offers_loader.canonicalize_account_id(
            "Universal", mapping, log_missing=False
        )
        self.assertEqual(account_id, "30141222")

        numeric_account = xlsx_offers_loader.canonicalize_account_id(
            "30137883_PP1", mapping, log_missing=False
        )
        self.assertEqual(numeric_account, "30137883")

    def test_store_header_detected(self) -> None:
        fake_config = self._fake_config()
        df = pd.DataFrame(columns=["Store_name", "SKU_ID_KSP", "Kaspi_art_1"])
        column_lookup = {
            xlsx_offers_loader._normalize_header(col): col for col in df.columns
        }
        store_col = xlsx_offers_loader._find_column(
            column_lookup, xlsx_offers_loader.STORE_HEADERS
        )
        self.assertEqual(store_col, "Store_name")

        with mock.patch("backend.ingest.xlsx_offers_loader.load_config", return_value=fake_config):
            store_map = xlsx_offers_loader.load_store_name_to_id_map()

        self.assertEqual(
            xlsx_offers_loader.canonicalize_account_id("Store_name", store_map, log_missing=False),
            "",
        )


if __name__ == "__main__":
    unittest.main()
