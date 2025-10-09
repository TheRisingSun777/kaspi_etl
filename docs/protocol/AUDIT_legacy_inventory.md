# AUDIT_legacy_inventory.md — Legacy Inventory Artifact Audit

## Scope
- Reviewed repository for manual inventory/CRM scripts, spreadsheets, and dashboards that diverge from the hybrid architecture in `docs/protocol/ARCHITECTURE.md`.
- Protected automations under `docs/ops/kaspi/` and other do-not-touch paths were inspected only for awareness; no files in those paths were modified.

## Legacy or Conflicting Artifacts

| Artifact | Path / Pattern | Conflict Type | Why it conflicts | Proposed action | Replacement |
| --- | --- | --- | --- | --- | --- |
| Manual stock snapshot CSV | `data_raw/stock_on_hand.csv` | manual dependency | Requires hand-edited counts and bypasses `stock_snapshots` aggregation | archive | Flow B `/inventory/update` → `stock_snapshots` (ARCHITECTURE.md, P2.1–P2.2) |
| Manual ActiveOrders export | `data_raw/ActiveOrders 31.7.25.xlsx` | manual dependency | Daily Excel download feeds downstream scripts instead of `/orders/ingest` | archive | Orders ingest API + `sales_daily` rollup (P3.1–P3.2) |
| Manual ArchiveOrders export | `data_raw/ArchiveOrders since 1.7.25.xlsx` | manual dependency | Long-term sales history maintained in spreadsheets instead of DB tables | archive | `sales_daily` + `demand_forecasts` (P3.2–P3.4) |
| Purchase inquiry tracker | `data_raw/Purchase inquiry made by me.xlsx` | manual dependency | Supplier pipeline tracked via ad-hoc Excel, not structured `purchases` records | refactor | `po_planner` inputs stored in DB (P5.1–P5.2) |
| Legacy stock ETL | `scripts/etl_stock.py` | manual dependency | Loads latest `stock*_*.csv` into SQLite, duplicating future Flow B ingestion | archive | Flow B `/inventory/update` pipeline (P2.1–P2.4) |
| Legacy orders ETL | `scripts/etl_sales.py` | manual dependency | Reads arbitrary `*orders*.xlsx` into SQLite instead of API/DB ingest | archive | `/orders/ingest` + `sales_daily` jobs (P3.1–P3.2) |
| Legacy purchases ETL | `scripts/etl_purchases.py` | manual dependency | Depends on Excel schema + SQLite writes that will be replaced by PO planning | refactor | Structured purchases loader tied to `po_plan` (P5.1) |
| Catalog ETL (simple) | `scripts/etl_catalog_simple.py` | duplicates | Another SQLite loader for catalog that conflicts with unified schema | archive | Central loader + migrations (P1.1, P1.3) |
| Catalog ETL (API) | `scripts/etl_catalog_api.py` | duplicates | Alternate API writer with its own DB shape; diverges from Python core | archive | Python core `products` module & future API client (P1.1, P2.1) |
| Enhanced catalog parser | `scripts/enhanced_catalog_parser.py` | duplicates | Third variant of catalog cleaning; overlaps with future canonical importer | refactor | Reconcile into single loader during P1.3 |
| Streamlit dashboard | `scripts/dashboard.py` | old pricing dash | UI depends on legacy SQLite tables and Streamlit runtime | archive | Analytics endpoints + reports (`analytics` module, P8.1) |
| Data files explainer | `scripts/explain_data_files.py` | outdated flow | Reinforces manual CSV/XLSX workflow targeted for retirement | archive | Updated operator docs post-P2/P3 (P9.1) |
| Size recommendation engine | `scripts/size_recommendation_engine.py` | outdated flow | Embeds legacy heuristics tied to SQLite instead of planned `size_engine` | refactor | Implement deterministic `size_engine` (P6.1) |
| Excel CRM importer | `docs/ops/kaspi/import_active_orders.py` | manual dependency | xlwings automation writing into `SALES_KSP_CRM_V3.xlsx`; bypasses new `/orders/ingest` | archive | Orders ingest + decision flow (P3.1, P6.3) |
| Import command wrappers | `docs/ops/kaspi/run_import_orders*.command` | manual dependency | Shell helpers orchestrate legacy Excel ETL pipeline | archive | One-click Flow A/B once Python core lands (P2.*, P3.*) |
| ActiveOrders archive dumps | `docs/ops/kaspi/ActiveOrders/archive_orders/` | manual dependency | Staged CSV copies from legacy append workflow; duplicates DB history | archive | Persist history via `orders`/`sales_daily` tables (P3.1–P3.2) |
| Legacy SQLite DB | `db/erp.db` | outdated flow | SQLite-only storage incompatible with Postgres target and new schema | archive | Structured migrations to Postgres (P1.1) |
| Manual data guide | `DATA_FILES_GUIDE.md` | outdated flow | Documents manual CSV control of stock/pricing contradicting new protocol | refactor | Update to reflect Python core & API sync (P9.1) |
| Automation analysis deck | `AUTOMATION_ANALYSIS.md` | outdated flow | Old roadmap assumes manual-first CSV ETL that conflicts with current GOALS | archive | Protocol-driven backlog (TASKS.yaml, future ADRs) |

## How We Will Transition
- Retire `data_raw/stock_on_hand.csv` and associated ETL scripts once Flow B `/inventory/update` (P2.1–P2.4) writes canonical `stock_snapshots`.
- Replace manual Active/Archive orders spreadsheets with `/orders/ingest` and `sales_daily` jobs delivered in P3.1–P3.2.
- Migrate catalog loaders into a single migration-backed importer during P1.1/P1.3; archive duplicate scripts after parity.
- Fold purchase inquiry tracking into the `po_plan` workflow (P5.1–P5.2) so supplier commitments live in the database.
- Supersede the Streamlit dashboard and Excel CRM automation with Python core analytics endpoints (P6.*, P8.*) and updated operator runbooks.
- Decommission the legacy SQLite database (`db/erp.db`) once migrations land; archive dumps for historical reference only.

## Scope Guard
- Protected automations in `docs/ops/kaspi/` remain intact; this audit documents conflicts but defers code changes until approved cleanup tasks (e.g., P9.1) begin. 
