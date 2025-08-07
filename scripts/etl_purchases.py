#!/usr/bin/env python3
# ----------  ETL FOR PURCHASE INQUIRY  ----------
import pandas as pd, sqlite3, pathlib

RAW_DIR = pathlib.Path(__file__).resolve().parents[1] / "data_raw"
DB_PATH = pathlib.Path(__file__).resolve().parents[1] / "db" / "erp.db"
con     = sqlite3.connect(DB_PATH)
cur     = con.cursor()

# 1 ──────────────────────────────────────────────────────────────────────────────
# Create / alter table
cur.execute("""
CREATE TABLE IF NOT EXISTS purchases (
  po_id            TEXT,
  sku_key          TEXT,
  order_date       DATE,
  arrival_date     DATE,
  qty              INTEGER,
  unit_cogs_kzt    REAL,
  freight_kzt      REAL,
  total_cogs_kzt   REAL,
  PRIMARY KEY (po_id, sku_key)
);
""")

# 2 ──────────────────────────────────────────────────────────────────────────────
# Process every Purchase‑Inquiry XLSX
for fp in RAW_DIR.glob("Purchase inquiry*.xlsx"):
    df_raw = pd.read_excel(fp)

    # Rename whatever column names the supplier used → canonical names
    rename_map = {
        'PO_Id'                         : 'po_id',
        'SKU_KEY'                       : 'sku_key',
        'PO_Date'                       : 'order_date',
        'Ast_arrival_date'              : 'arrival_date',
        'Qty'                           : 'qty',
        'Total_model_order_qty'         : 'qty',          # fallback name
        'Unit_COGS_KZT'                 : 'unit_cogs_kzt',
        'Total_Model_DeliveryCost_KZT'  : 'freight_kzt',
        'Total_Model_FreightCost_KZT'   : 'total_cogs_kzt'
    }
    df = df_raw.rename(columns=rename_map)

    # Convert dates safely
    df['order_date']   = pd.to_datetime(df['order_date'],   errors='coerce').dt.date
    df['arrival_date'] = pd.to_datetime(df['arrival_date'], errors='coerce').dt.date

    # Keep only the columns we need
    cols = ['po_id','sku_key','order_date','arrival_date',
            'qty','unit_cogs_kzt','freight_kzt','total_cogs_kzt']
    df = df[cols]

    # Drop duplicate lines inside the same file
    df = df.drop_duplicates(subset=['po_id','sku_key'])

    # UPSERT: delete old rows for these (po_id, sku_key) pairs then insert
    ids = list(df[['po_id','sku_key']].itertuples(index=False, name=None))
    if ids:
        cur.executemany(
            "DELETE FROM purchases WHERE po_id=? AND sku_key=?",
            ids
        )
    df.to_sql("purchases", con, if_exists='append', index=False)

con.commit()
con.close()
print("✅  Purchases loaded")