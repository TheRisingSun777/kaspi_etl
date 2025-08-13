.PHONY: bundle

bundle:
	./scripts/make_repo_bundle.sh

.PHONY: orders

orders:
	@echo "Running ETL for active orders..."
	@python scripts/etl_orders_api.py
	@python scripts/api_orders_to_csv.py
	@python scripts/join_api_orders_to_sales.py

.PHONY: group-labels

group-labels:
	@echo "Grouping Kaspi label PDFs by SKU and size..."
	@./venv/bin/python scripts/crm_kaspi_labels_group.py --input "$(INPUT)" $(if $(PROCESSED),--processed "$(PROCESSED)") $(if $(OUT_DATE),--out-date "$(OUT_DATE)")
