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

- 2025-08-14 — CI strict checks updated and run.
  - Strict: orders required columns + >=95% non-null; processed sku_id rule; size-recs rec_size >=95%; KSP map schema; size grids presence.
  - Result: PASS except size grids missing in this branch (expected); overall ❌ due to grids absence.

- 2025-08-14 — Added end-to-end runner.
  - `scripts/run_e2e.sh` with orders → join → size-recs → (labels if INPUT) → picklist.
  - Make `run-all`: `make run-all INPUT=~/Downloads/waybill-327.zip OUT_DATE=$(date +%F)`

- 2025-08-14 — Checkpoint & rotate.
  - Labels grouping improved (orderid/join_code/product_master_code); WA handoff is manual-confirm; size-recs from processed; CI strict wired; orders ETL now env-tunable with paging/retry. Next: add API token and run live orders.

- 2025-08-14 — WA outbox handoff (manual-confirm).
  - `scripts/wa_send_files.applescript` + `scripts/wa_send_outbox.py` to open WhatsApp, attach PDFs from latest labels folder to target chat.
  - Make `outbox`: requires `PHONE=+7...` env; script leaves messages composed — press Enter to send.

- 2025-08-14 — Join hardened: tolerant mapping + missing mapping report.
  - `scripts/join_api_orders_to_sales.py` now maps by (ksp_sku_id, store) → (product_master_code, store) → ksp_sku_id → product_master_code.
  - Writes `data_crm/reports/missing_ksp_mapping.csv` with guessed model group; `sku_id` only when both sku_key and my_size present.

- 2025-08-14 — Size-recs: prefer API CSV; honor my_size; strict null gate.
  - `scripts/link_orders_and_sizes.py` now prioritizes `orders_api_latest.csv`, then newest `active_orders_*.csv/xlsx`.
  - Uses my_size if provided; else engine(height,weight); else size grids; regex model_group.
  - Make `size-recs` prints first 20 with both sku_key and rec_size; fails if rec_size null-rate > 10%.

- 2025-08-14 — Labels grouping: map by PDF order number; grouped outputs + manifest.
  - `scripts/crm_kaspi_labels_group.py` extracts 7–12 digit order from filename, joins to orders staging, groups by (sku_key,my_size), stable-merge PDFs.
  - Outputs to `data_crm/labels_grouped/${OUT_DATE}/` with `{clean_model}_{my_size}-{count}.pdf`, writes `manifest.csv` and `unmatched_files.txt`.

- 2025-08-14 — Orders ETL: real paging + filter + staging outputs.
  - `scripts/etl_orders_api.py` adds paging (page,size), optional status filter, polite sleep, first 5 ids/sku logs.
  - Saves raw JSON to `data_crm/inputs/orders_active_YYYYMMDD.json` and normalized to both dated + `orders_api_latest.csv`.

- 2025-08-14 — CI: enforce size/mapping gates.
  - `scripts/ci_sanity.py` checks: orders non-empty; size-recs null-rate <10%; missing_ksp_mapping rows == 0 or <5% of orders.
  - Make `ci-sanity` runs strict mode.

- 2025-08-14 — Waybills downloader (cookie-based).
  - Added `scripts/kaspi_waybills_download.py` using KASPI_MERCHANT_COOKIE; saves `data_crm/inputs/waybill_YYYYMMDD.zip`.
  - Make `waybills` target added.

- 2025-08-14 — Outbox packer.
  - Added `scripts/crm_outbox_pack.py` to copy grouped PDFs to `outbox/${OUT_DATE}/` and write counts summary.
  - Make `outbox` now packs from labels_grouped.
