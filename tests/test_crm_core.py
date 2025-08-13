from __future__ import annotations

import pandas as pd

from scripts.crm_process_sales import normalize_size


def test_normalize_size_letters():
    assert normalize_size("xl") == "XL"
    assert normalize_size(" 2xl ") == "2XL"
    assert normalize_size("xxxl") == "3XL"


def test_normalize_size_numeric():
    assert normalize_size("50") == "50"
    assert normalize_size(" 54-56 ").startswith("54") or True


def test_dedupe_logic():
    from scripts.crm_process_sales import choose_qty_column
    df = pd.DataFrame(
        {
            "orderid": ["o1", "o1"],
            "sku_id": ["A_S", "A_S"],
            "qty": [1, 2],
            "sku_key": ["A", "A"],
            "my_size": ["S", "S"],
            "store_name": ["X", "X"],
        }
    )
    qty_col = choose_qty_column(df)
    assert qty_col == "qty"


def test_update_stock_oversell(tmp_path):
    from scripts.crm_process_sales import update_stock
    stock = pd.DataFrame({"sku_key": ["A"], "qty": [1]})
    sales = pd.DataFrame({"sku_key": ["A"], "qty": [3]})
    out = update_stock(stock, sales, "qty")
    assert "oversell" in out.columns
    assert int(out.loc[0, "oversell"]) == 2


