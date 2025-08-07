#!/usr/bin/env python3
# ----------  ETL FOR PHYSICAL STOCK SNAPSHOT ----------
import pandas as pd, sqlite3, pathlib, sys

ROOT     = pathlib.Path(__file__).resolve().parents[1]
RAW_DIR  = ROOT / "data_raw"
DB_PATH  = ROOT / "db" / "erp.db"

# ── locate the newest stock_*.csv ───────────────────────
try:
    stock_fp = max(RAW_DIR.glob("stock*_*.csv"), key=lambda p: p.stat().st_mtime)
except ValueError:
    sys.exit("No stock_*.csv file found in data_raw/")

# ── load & clean ────────────────────────────────────────
df = pd.read_csv(stock_fp, dtype={"sku_key": str, "qty_on_hand": int})
df["sku_key"] = df["sku_key"].str.strip().str.upper()

# ── write to SQLite ─────────────────────────────────────
con = sqlite3.connect(DB_PATH)
df.to_sql("stock", con, if_exists="replace", index=False)
con.close()
print(f"✅  Stock loaded: {len(df):,} rows from {stock_fp.name}")