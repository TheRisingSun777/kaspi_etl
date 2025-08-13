# Progress Tracker

- 2025-08-14 — Initialized repo bundle tooling (commit bed9d9f).
  - Added `.gitattributes` export-ignore rules for clean archives.
  - Added `scripts/make_repo_bundle.sh` and `Makefile` target `bundle`.
  - Pushed to `kaspi-api-integration`.

- 2025-08-14 — Grouped label PDFs by SKU and size (feat).
  - Added `scripts/crm_kaspi_labels_group.py` using processed sales mapping.
  - New Makefile target `group-labels`.
  - Outputs under `data_crm/labels_grouped/YYYY-MM-DD/` with `manifest.csv`.

- 2025-08-14 — Restored API orders staging/join pipeline and updated size-link.
  - Restored `scripts/api_orders_to_csv.py`, `scripts/join_api_orders_to_sales.py`, `scripts/link_orders_and_sizes.py`.
  - Make `orders` now chains ETL → staging → join.
  - `link_orders_and_sizes.py` prefers `data_crm/orders_api_latest.csv` and writes real `rec_size`.

- 2025-08-14 — ETL hardening + cache run (orders→CSV→join→sizes→picklist).
  - `api_orders_to_csv.py`: added --input/INPUT_JSON, webhook_* fallback, strict JSON error handling.
  - `join_api_orders_to_sales.py`: robust sku_key join; emits `data_crm/reports/missing_ksp_mapping.csv` if gaps.
  - Make targets: `orders-from-cache`, `sanity`, restored `size-recs`.
  - Ran with cache JSON; produced `processed_sales_latest.csv`, `orders_kaspi_with_sizes.xlsx`, and picklist files.

- 2025-08-14 — CI sanity script and target.
  - Added `scripts/ci_sanity.py` and Make target `ci-sanity` (uses venv python if present).
  - First run output:
    - CRITICAL ok: orders_api_latest.csv
    - CRITICAL missing: mappings/ksp_sku_map_updated.xlsx
    - IMPORTANT ok: processed_sales_latest.csv, orders_kaspi_with_sizes.xlsx
    - Non-null/format checks: PASS (100% non-null, 0 mismatches)

- 2025-08-14 — size-recs prefers API orders; robust input + columns.
  - `link_orders_and_sizes.py`: prefer `data_crm/orders_api_latest.csv`, fallback to newest `active_orders_*`.
  - Fills `sku_key` from `product_master_code` when missing; ensures output columns.
  - Make `size-recs` uses venv python and prints a CSV preview of the first 20 rows.

- 2025-08-14 — Labels grouping resilient; manifest embedded.
  - `crm_kaspi_labels_group.py`: extracts orderid from filename or PDF text (7+ digits), maps via processed then API orders.
  - Groups to `{sku_key}_{my_size or UNK}.pdf`; writes `manifest.csv` with [pdf_file, orderid, sku_key, my_size, group_file].
  - Make `group-labels` prints first 30 manifest rows.

- 2025-08-14 — Outbox bundler for fulfillment handoff.
  - Added `scripts/outbox_pack.py` and `make outbox`.
  - Produces `outbox/YYYY-MM-DD/bundle_YYYY-MM-DD.zip` with grouped labels, picklist.pdf, and README.txt.

- 2025-08-14 — Waybills fetcher (Merchant Cabinet) with Playwright.
  - Added `scripts/fetch_waybills_mc.py` using cookie auth; `make fetch-waybills` target.
  - Saves ZIP under `data_crm/labels_inbox/YYYY-MM-DD/waybill-*.zip`.

- 2025-08-14 — Size linker prefers API CSV; stronger model inference.
  - `link_orders_and_sizes.py` prioritizes `orders_api_latest.csv`, then newest `active_orders_*`.
  - Fills `sku_key` from `product_master_code`, then `ksp_sku_id`; improved `model_group` inference.
  - Top 20 preview prints `[orderid, sku_key, height, weight, rec_size]`.
