#!/usr/bin/env bash
set -e

./scripts/run_db_migrations.sh
./venv/bin/python scripts/sync_orders_api_to_db.py --from $(date -v-7d +%F) --to $(date +%F) --state NEW
./venv/bin/python scripts/size_workflow.py
./venv/bin/python scripts/crm_build_packing_pdfs.py
./venv/bin/python scripts/plan_stock_delta.py
./venv/bin/python scripts/kaspi_stock_update.py
./venv/bin/python scripts/plan_order_status.py
./venv/bin/python scripts/apply_order_status.py
./venv/bin/python scripts/crm_status_report.py
./venv/bin/python scripts/crm_alerts.py

