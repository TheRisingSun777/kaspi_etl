.PHONY: repair process labels loaddb daily picklist exportbm validate

PY=./venv/bin/python

repair:
	$(PY) scripts/crm_repair_sales.py

process:
	$(PY) scripts/crm_process_sales.py

labels:
	./scripts/run_build_labels.sh

loaddb:
	$(PY) scripts/crm_load_to_db.py

daily:
	./scripts/run_daily.sh

picklist:
	$(PY) scripts/crm_build_picklist.py

exportbm:
	$(PY) scripts/export_for_business_model.py

validate:
	$(PY) scripts/validate_phase1_data.py


