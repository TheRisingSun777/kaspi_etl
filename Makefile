.PHONY: setup lint test repair process labels loaddb daily picklist exportbm validate mart bundle

PY=./venv/bin/python

setup:
	python3 -m venv venv
	./venv/bin/pip install -U pip
	./venv/bin/pip install -r requirements.txt -r requirements-dev.txt
	./venv/bin/pre-commit install

lint:
	./venv/bin/ruff check .
	./venv/bin/black --check .

repair:
	$(PY) scripts/crm_repair_sales.py

process:
	$(PY) -m scripts.crm_cli process-sales

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

test:
	pytest -q

mart:
	$(PY) -m scripts.crm_build_mart

bundle:
	./scripts/make_repo_bundle.sh


