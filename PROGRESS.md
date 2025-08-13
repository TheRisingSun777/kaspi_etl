# Progress Tracker

- 2025-08-14 — Initialized repo bundle tooling (commit bed9d9f).
  - Added `.gitattributes` export-ignore rules for clean archives.
  - Added `scripts/make_repo_bundle.sh` and `Makefile` target `bundle`.
  - Pushed to `kaspi-api-integration`.

- 2025-08-14 — Grouped label PDFs by SKU and size (feat).
  - Added `scripts/crm_kaspi_labels_group.py` using processed sales mapping.
  - New Makefile target `group-labels`.
  - Outputs under `data_crm/labels_grouped/YYYY-MM-DD/` with `manifest.csv`.
