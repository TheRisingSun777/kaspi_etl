Phase 1 Operations (CRM)

- Where to place files
  - Put latest sales: `data_crm/sales_ksp_crm_20250813_v1.xlsx` (or the fixed file the script writes)
  - Put latest stock: `data_crm/stock_on_hand.csv`

- Run Phase 1
  - Repair sales (normalize sizes, fix keys):
    `./venv/bin/python scripts/crm_repair_sales.py`
  - Process sales (update stock, logs, coverage):
    `./venv/bin/python scripts/crm_process_sales.py`
  - Build labels (if applicable):
    `./scripts/run_build_labels.sh`

- Makefile shortcuts
  - `make repair` → repair sales
  - `make process` → process sales
  - `make labels` → build labels
  - `make loaddb` → load to SQLite (erp.db)
  - `make daily` → run full daily orchestrator
  - `make picklist` → generate warehouse picklist (CSV/PDF)
  - `make exportbm` → export CSV for business_model.xlsm
  - `make validate` → run validation suite

- Checkpoint / rotate
  - Append a short summary to `docs/PROGRESS.md`
  - Persist run state to `STATE.json`
  - Update `docs/TASKS.yaml` statuses

