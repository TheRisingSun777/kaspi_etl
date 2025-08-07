#!/usr/bin/env python3
import streamlit as st, pandas as pd, sqlite3, pathlib, altair as alt
DB=pathlib.Path(__file__).parents[1]/"db"/"erp.db"

@st.cache_data(ttl=300)
def load():
    con=sqlite3.connect(DB)
    orders=pd.read_sql("select * from orders",con,parse_dates=['order_date'])
    con.close()
    return orders

orders=load()

st.title("Kaspi Mini‑Dashboard")

col1,col2=st.columns(2)
col1.metric("Orders",f"{len(orders):,}")
col2.metric("Net revenue",f"{(orders['gross_price_kzt']*(1-orders['kaspi_fee_pct'])-orders['delivery_cost_kzt']).sum():,.0f} ₸")

st.subheader("Daily Net Revenue")
rev=(orders.assign(net=lambda d:d['gross_price_kzt']*(1-d['kaspi_fee_pct'])-d['delivery_cost_kzt'])
          .groupby('order_date')['net'].sum().reset_index())
st.altair_chart(alt.Chart(rev).mark_bar().encode(x='order_date:T',y='net:Q'),
                use_container_width=True)

st.subheader("Gross Margin by SKU")
pivot=(orders.assign(net=lambda d:d['gross_price_kzt']*(1-d['kaspi_fee_pct'])-d['delivery_cost_kzt'])
              .groupby('sku_key')['net'].sum().sort_values(ascending=False).reset_index())
st.dataframe(pivot,use_container_width=True)