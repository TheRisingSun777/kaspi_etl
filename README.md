### Kaspi CRM ETL (crm-system)

Quick start

- make setup
- make process
- make mart
- make test

File layout (key paths)

- data_crm/: inputs, outputs, reports, state
  - processed_sales_latest.csv; processed/processed_sales_YYYYMMDD.csv
  - stock_on_hand_updated.csv; stock/stock_on_hand_updated_YYYYMMDD.csv
  - reports/: missing_skus_YYYYMMDD.csv, duplicates_YYYYMMDD.csv, oversell_YYYYMMDD.csv, KPI reports
  - mart/: dim_*.csv, fact_sales_YYYYMMDD.csv
  - state/: runlog_YYYYMMDD.jsonl, last_error.txt, STATE.json (reserved)
- scripts/: CLI and pipeline steps
  - crm_cli.py, crm_process_sales.py, crm_build_mart.py, crm_kpi_reports.py
- config/crm.yml: paths, aliases, size map; .env/.env.local for overrides (RUN_DATE)

Run examples

- Process sales: make process
- Build data mart: make mart
- KPI reports: ./venv/bin/python scripts/crm_kpi_reports.py
- Daily orchestrator: make daily

Glossary (size/sku)

- sku_key: model identifier (upper snake case), no size
- my_size: normalized size label (S/M/L/XL/2XL/… or numeric 44–64)
- sku_id: join key sku_key + '_' + my_size (blank if missing sku_key)

Docs

- See docs/DATA_DICTIONARY.md and docs/PIPELINE.md


