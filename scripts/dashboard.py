#!/usr/bin/env python3
# ----------  Streamlit mini‑dashboard ----------
import streamlit as st, pandas as pd, sqlite3, pathlib, altair as alt, numpy as np

DB = pathlib.Path(__file__).parents[1] / "db" / "erp.db"

# ---------- helpers ----------
def reorder_point(daily, lead, z=1.65):          # 95 % service level ≈ z‑score 1.65
    safety = z * (daily * 0.2) * np.sqrt(lead)   # assume 20 % demand st.dev. if none given
    return int(np.ceil(daily * lead + safety))

# ---------- data loaders ----------
@st.cache_data(ttl=300)
def load():
    con = sqlite3.connect(DB)
    orders = pd.read_sql("select * from orders", con, parse_dates=["order_date"])
    try:
        stock = pd.read_sql("select * from stock", con)
    except Exception:
        stock = pd.DataFrame(columns=["sku_key", "qty_on_hand"])
    con.close()
    return orders, stock

orders, stock = load()

# ---------- KPI tiles ----------
col1, col2 = st.columns(2)
col1.metric("Orders", f"{len(orders):,}")
col2.metric(
    "Net revenue",
    f"{(orders['gross_price_kzt']*(1-orders['kaspi_fee_pct'])-orders['delivery_cost_kzt']).sum():,.0f} ₸",
)

# ---------- Inventory panel ----------
recent = orders[orders["order_date"] >= orders["order_date"].max() - pd.Timedelta(days=30)]
daily_demand = (recent.groupby("sku_key")["qty"].sum() / 30).rename("daily_demand")

inv = stock.merge(daily_demand, on="sku_key", how="left").fillna({"daily_demand": 0})
inv["rop"] = inv.apply(lambda r: reorder_point(r["daily_demand"], 20), axis=1)
inv["need_reorder"] = inv["qty_on_hand"] <= inv["rop"]

st.subheader("Inventory & ROP")
st.dataframe(
    inv[["sku_key", "qty_on_hand", "rop", "need_reorder"]]
        .sort_values("need_reorder", ascending=False),
    use_container_width=True,
)

# ---------- Daily net revenue chart ----------
st.subheader("Daily Net Revenue")
rev = (
    orders.assign(net=lambda d: d["gross_price_kzt"] * (1 - d["kaspi_fee_pct"]) - d["delivery_cost_kzt"])
          .groupby("order_date")["net"]
          .sum()
          .reset_index()
)

chart = (
    alt.Chart(rev)
       .mark_bar()
       .encode(x="order_date:T", y="net:Q")
       .properties(height=250)
)
st.altair_chart(chart, use_container_width=True)

# ---------- Gross margin by SKU ----------
pivot = (
    orders.assign(net=lambda d: d["gross_price_kzt"] * (1 - d["kaspi_fee_pct"]) - d["delivery_cost_kzt"])
          .groupby("sku_key")["net"]
          .sum()
          .reset_index()
          .sort_values("net", ascending=False)
)
st.subheader("Gross Margin by SKU")
st.dataframe(pivot, use_container_width=True)