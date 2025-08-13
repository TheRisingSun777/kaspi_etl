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
