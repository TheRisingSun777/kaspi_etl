# Progress Tracker

- 2025-08-14 — Initialized repo bundle tooling (commit bed9d9f).
  - Added `.gitattributes` export-ignore rules for clean archives.
  - Added `scripts/make_repo_bundle.sh` and `Makefile` target `bundle`.
  - Pushed to `kaspi-api-integration`.
 
- 2025-08-14 — Brought CRM paths from `crm-system` into safety branch `crm-api-join` (commit bc47e1b).
  - Checked out `data_crm/` and key CRM scripts into the API worktree.
  - Pushed branch `crm-api-join` to origin.

- 2025-08-14 — Env bootstrap for API tests.
  - Updated `.env.example` to include KASPI_BASE and token aliases.
  - `scripts/test_kaspi_api.py` now loads `.env.local` and supports multiple token var names.
  - Ran test: waiting on token in `.env.local` (missing token detected as expected).

- 2025-08-14 — Orders intake ETL (commits b1ed662, 4e378f5).
  - Added `scripts/etl_orders_api.py` to pull active orders and normalize to CSV/XLSX.
  - Added `make orders` target.
  - First run pending token in `.env.local`.

- 2025-08-14 — Link API orders to size recommendations (commit 74ba615).
  - Added `scripts/link_orders_and_sizes.py` and `make size-recs` target.
  - Outputs `data_crm/orders_kaspi_with_sizes.xlsx` (currently defaults due to missing grids and sparse source columns).

- 2025-08-14 — API orders → CSV staging (commit f7ed1eb).
  - Added `scripts/api_orders_to_csv.py` to flatten latest `data_crm/api_cache/orders_*.json` into `data_crm/orders_api_latest.csv`.
  - No cache files present yet; script no-ops safely.

- 2025-08-14 — P-FIX-1: Verified `data_crm` present in `crm-api-join`; no checkout required.

- 2025-08-14 — P-RUN-A: Smoke run attempted; API orders step timing out.
  - Added retries, headers, paging (size=25). Still ReadTimeout/ReadError from Kaspi orders endpoint.
  - Next: retry with `KASPI_ORDERS_STATUS=ACCEPTED_BY_MERCHANT` and smaller size (e.g., 5), or use cached JSON.

- 2025-08-14 — Reports: missing KSP mapping.
  - Added `scripts/report_missing_ksp_mapping.py` and `make report-missing-maps`.
  - Generated `data_crm/reports/missing_ksp_mapping.csv` (empty headers if no gaps).

- 2025-08-14 — Exports: grouped packing PDFs.
  - Added `scripts/crm_group_pdfs.py` and `make pack-pdfs`; produced per-group CSV/PDF and `pack_all_groups.pdf`.
  - Added `zip-exports` target → `outbox/exports_YYYYMMDD_HHMM.zip`.

- 2025-08-14 — WhatsApp Web helper (semi-auto).
  - Added `services/whatsapp_web.py` and `make wa-open`.
  - Opens chat and prompts to drag ZIP/PDF; no auto-upload.

- 2025-08-14 — Webhook stub service.
  - Added FastAPI `services/api_server.py` with `/health` and `/orders/ingest` (saves to `data_crm/api_cache/`).
  - `make serve` starts on port 3801.

- 2025-08-14 — Strict processed_sales schema.
  - `join_api_orders_to_sales.py` enforces canonical header; writes `data_crm/reports/schema_diff.txt` on mismatch.
  - Processed/stock regenerated from cached JSON; coverage updated.

- 2025-08-14 — size-recs runs off processed sales; non-null rec_size.
  - Updated `scripts/link_orders_and_sizes.py` to prioritize processed sales, derive `model_group`, normalize sizes, and use grid/engine defaults.
  - Wrote `data_crm/orders_kaspi_with_sizes.xlsx` with [orderid, date, ksp_sku_id, sku_key, store_name, qty, height, weight, rec_size, model_group].
  - Sample run: rec_size counts show non-null values (defaults to M where needed).
