"""
Export processed sales into an Excel-friendly CSV for business_model.xlsm import.

Input:
- data_crm/processed_sales_20250813.csv

Output:
- data_crm/exports/business_model_sales_import.csv with columns:
  OrderID,Date,Product_Category,MODEL,SKU_ID,Qty,SellPrice_KZT,ChannelID,FX_RUBKZT

Rules:
- Fill unknown fields with blanks
- Date formatted as YYYY-MM-DD

Run:
  ./venv/bin/python scripts/export_for_business_model.py
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_CSV = REPO_ROOT / "data_crm" / "processed_sales_20250813.csv"
OUT_DIR = REPO_ROOT / "data_crm" / "exports"
OUT_CSV = OUT_DIR / "business_model_sales_import.csv"


def load_processed() -> pd.DataFrame:
    if not SRC_CSV.exists():
        raise FileNotFoundError(f"Missing input: {SRC_CSV}")
    df = pd.read_csv(SRC_CSV)
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def to_business_model(df: pd.DataFrame) -> pd.DataFrame:
    # Map available fields
    orderid = df.get("orderid")
    date_raw = pd.to_datetime(df.get("date"), errors="coerce")
    date_fmt = date_raw.dt.strftime("%Y-%m-%d")
    sku_id = df.get("sku_id")
    qty = pd.to_numeric(df.get("qty"), errors="coerce")
    sell_price = pd.to_numeric(df.get("sell_price"), errors="coerce")

    out = pd.DataFrame(
        {
            "OrderID": orderid.astype(str).where(orderid.notna(), ""),
            "Date": date_fmt.where(date_fmt.notna(), ""),
            "Product_Category": "",
            "MODEL": "",
            "SKU_ID": sku_id.astype(str).where(sku_id.notna(), ""),
            "Qty": qty.fillna(0).astype(int),
            "SellPrice_KZT": sell_price.where(sell_price.notna(), ""),
            "ChannelID": "",
            "FX_RUBKZT": "",
        }
    )
    return out


def main() -> int:
    df = load_processed()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    export_df = to_business_model(df)
    export_df.to_csv(OUT_CSV, index=False)
    print(f"Export written: {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


