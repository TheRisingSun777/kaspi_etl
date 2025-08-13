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

.PHONY: zip-exports

zip-exports:
	@echo "Zipping data_crm/exports to outbox/ ..."
	@mkdir -p outbox
	@stamp=$$(date +%Y%m%d_%H%M); out="outbox/exports_$${stamp}.zip"; \
		echo "Creating $$out"; \
		zip -r "$$out" data_crm/exports >/dev/null; \
		echo "$$out"

.PHONY: wa-open

wa-open:
	@echo "Opening WhatsApp Web to target chat..."
	@./venv/bin/python -m services.whatsapp_web --to "$(TO)" --attach "$(ATTACH)"

.PHONY: show-schedule

show-schedule:
	@echo 'Save as ~/Library/LaunchAgents/com.kaspi.etl.daily.plist:'
	@cat docs/OPERATING.md | sed -n '/^```xml/,/^```/p' | sed '1d;$d'
