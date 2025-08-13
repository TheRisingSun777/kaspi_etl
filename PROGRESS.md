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
