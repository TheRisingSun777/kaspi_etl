# ISSUES.md — Bugs / Risks / Technical Debt

## Open
- [ ] #1 Legacy inventory conflicts. Owner: codex. Opened: 2025-10-07 13:09
  - `data_raw/stock_on_hand.csv` + `scripts/etl_stock.py`: archive after Flow B `/inventory/update` (P2.1–P2.4) lands.
  - `data_raw/ActiveOrders 31.7.25.xlsx` + `scripts/etl_sales.py` + `docs/ops/kaspi/import_active_orders.py`: replace with `/orders/ingest` + `sales_daily` (P3.1–P3.2).
  - `data_raw/ArchiveOrders since 1.7.25.xlsx` + `docs/ops/kaspi/ActiveOrders/archive_orders/`: migrate history into DB via P3.2–P3.4.
  - `data_raw/Purchase inquiry made by me.xlsx` + `scripts/etl_purchases.py`: refactor into `po_plan` workflow (P5.1–P5.2).
  - Catalog loaders (`scripts/etl_catalog_simple.py`, `scripts/etl_catalog_api.py`, `scripts/enhanced_catalog_parser.py`): consolidate under P1.1/P1.3 migrations.
  - `scripts/dashboard.py`: deprecate once analytics endpoints (P8.1) deliver replacements.
  - Manual docs/scripts (`scripts/explain_data_files.py`, `DATA_FILES_GUIDE.md`, `AUTOMATION_ANALYSIS.md`): refresh during P9.1 documentation cleanup.
  - `scripts/size_recommendation_engine.py`: align with deterministic `size_engine` (P6.1).
  - `db/erp.db`: retire after database migrations and Postgres cutover (P1.1).

## Closed
