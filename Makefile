.PHONY: bundle

bundle:
	./scripts/make_repo_bundle.sh

.PHONY: orders

orders:
	@echo "Running ETL for active orders..."
	@python scripts/etl_orders_api.py

.PHONY: size-recs

size-recs:
	@echo "Linking orders with size recommendations..."
	@./venv/bin/python scripts/link_orders_and_sizes.py

.PHONY: report-missing-maps

report-missing-maps:
	@echo "Reporting missing KSP mappings (sku_key gaps)..."
	@python scripts/report_missing_ksp_mapping.py

.PHONY: pack-pdfs

pack-pdfs:
	@echo "Generating grouped packing PDFs and manifest..."
	@./venv/bin/python scripts/crm_group_pdfs.py
