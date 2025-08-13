#!/usr/bin/env python3
# --- ETL FOR KASPI ORDERS  (v2025‑08‑03) -----------------------------------
import pathlib
import re
import sqlite3

import pandas as pd

RAW_DIR  = pathlib.Path(__file__).resolve().parents[1] / "data_raw"
DB_PATH  = pathlib.Path(__file__).resolve().parents[1] / "db" / "erp.db"
MAP_PATH = RAW_DIR / "M02_SKU_CATALOG Sample for gpt.csv"

# 0 ── Load SKU mapping (semicolon CSV, robust) ──────────────────────────────
if MAP_PATH.exists():
    map_df = (
        pd.read_csv(MAP_PATH, sep=';', engine='python', dtype=str,
                    on_bad_lines='skip')
        .rename(columns={'SKU_key':'sku_key',
                         'Weight_kg':'weight_kg',
                         'sku_name_raw':'sku_name_raw'})
        .assign(
            sku_name_raw=lambda d: d['sku_name_raw'].str.strip(),
            weight_g=lambda d: pd.to_numeric(
                d['weight_kg'].str.replace(',', '.'),
                errors='coerce') * 1000
        )[["sku_name_raw","sku_key","weight_g"]]
    )
else:
    map_df = pd.DataFrame(columns=["sku_name_raw","sku_key","weight_g"])

# 1 ── Delivery‑fee calculator ───────────────────────────────────────────────
def calc_delivery(row):
    price = row["gross_price_kzt"]
    kg    = row.get("weight_g", 0) / 1000 if pd.notna(row.get("weight_g")) else 0
    base = 0 if price >= 15000 else 699 if price >= 10000 else 799 if price >= 5000 else 999
    extra = max(0, int(-(-kg // 1)) - 3) * 399   # charges after 3 kg
    return base + extra

# 2 ── Read every *orders*.xlsx ──────────────────────────────────────────────
def order_files():
    for fp in RAW_DIR.iterdir():
        if "orders" in fp.name.lower() and fp.suffix.lower()==".xlsx":
            yield fp

frames=[]
for fp in order_files():
    df = pd.read_excel(fp)

    df.columns=[re.sub(r'\s+','_',c.strip()).lower() for c in df.columns]
    df=df.rename(columns={
        '№_заказа':'order_id',
        'дата_поступления_заказа':'order_date',
        'дата_изменения_статуса':'status_date',
        'статус':'status',
        'название_товара_в_kaspi_магазине':'sku_name_raw',
        'количество':'qty',
        'сумма':'gross_price_kzt'
    },errors='ignore')

    df=df[['order_id','order_date','status_date','status',
           'sku_name_raw','qty','gross_price_kzt']]

    df['order_date']=pd.to_datetime(df['order_date'],dayfirst=True,errors='coerce').dt.date
    df['status_date']=pd.to_datetime(df['status_date'],dayfirst=True,errors='coerce').dt.date
    df['kaspi_fee_pct']=0.12
    df['sku_name_raw']=df['sku_name_raw'].astype(str).str.strip()

    df=df.merge(map_df,on='sku_name_raw',how='left')
    df['sku_key']=df['sku_key'].fillna(df['sku_name_raw'].str.upper())
    df['delivery_cost_kzt']=df.apply(calc_delivery,axis=1)

    frames.append(df)

if not frames:
    raise SystemExit("⚠️  No *orders* files found in data_raw/")

orders=pd.concat(frames,ignore_index=True)

# 3 ── Write / replace table ────────────────────────────────────────────────
sqlite3.connect(DB_PATH).execute("DROP TABLE IF EXISTS orders;").close()
con=sqlite3.connect(DB_PATH)
orders.to_sql("orders",con,if_exists='replace',index=False)
con.close()
print(f"✅  Orders loaded: {len(orders):,} rows")