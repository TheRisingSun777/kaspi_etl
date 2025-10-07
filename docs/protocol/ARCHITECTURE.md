# ARCHITECTURE.md — Hybrid System

## Components
- **Python Core (repo)**: FastAPI + jobs + DB (SQLite→Postgres later)
  - Modules: inventory_sync, orders, whatsapp_inbox, size_engine, forecast, policy, po_planner, pdf_labels, analytics
  - DB: products, offer_to_sku_key, stock_snapshots, sales_daily, orders, size_mix, demand_forecasts, diagnostics, inventory_policy, po_plan
- **n8n (thin glue)**:
  - Flow A: Orders→15:00 gate→WhatsApp send→/wa/parse webhook→/decide
  - Flow B: Inventory poll (all stores)→POST /inventory/update→apply enable/disable via Kaspi API→notify
- **External**: Kaspi Merchant API (offers, stock, orders), WhatsApp provider (Algatop now; Cloud/Twilio later)

## API Contracts (Python)
- `POST /inventory/update`
  - req: `[ {offer_id, account_id, qty}, ... ]`
  - res: `[ {offer_id, account_id, action: 'ENABLE'|'DISABLE', reason }, ... ]`
- `POST /orders/ingest`
  - req: orders payload (from API or CSV fallback), upsert into DB
  - res: counts
- `POST /wa/parse` (webhook)
  - req: `{order_id, text, phone, ts}`
  - res: `{parsed: {height_cm, weight_kg, pref_size?}, status}`
- `POST /decide`
  - req: `{order_id, reply_missing: bool}`
  - res: `{final_size, decision_reason, boundary_flag}`
- `POST /labels/build`
  - req: `{order_ids:[...]}` or uploaded ZIP; groups/merges PDFs; returns file handle/link
- `GET /report/inventory`, `GET /report/po`, `GET /report/kpis` — CSV/JSON summaries

## Data Spine
- `offer_to_sku_key(offer_id PK, account_id, sku_key)`
- `stock_snapshots(sku_key, account_id, qty, ts_utc)`
- `sales_daily(sku_key, date, qty)`
- `size_mix(sku_key, size, share)`
- `demand_forecasts(sku_key, D_current, sigma_90, updated_at)`
- `po_plan(po_id, sku_key, alloc_json_by_size, t_post_days, created_at, status)`

## Flow B (Inventory/OOS)
Kaspi→n8n poll → /inventory/update → aggregate per sku_key → action list → n8n apply enable/disable → notify

## Flow A (Orders & Sizes)
Kaspi→n8n intake → WhatsApp send → webhook /wa/parse → /decide (<=15:00 gate) → update order + stock → /labels/build → notify
