.PHONY: bundle

bundle:
	./scripts/make_repo_bundle.sh

.PHONY: orders

orders:
	@echo "Running ETL for active orders..."
	@echo "Params: KASPI_ORDERS_STATUS='$(KASPI_ORDERS_STATUS)' KASPI_ORDERS_SIZE='$(KASPI_ORDERS_SIZE)'"
	@./venv/bin/python scripts/etl_orders_api.py

.PHONY: size-recs

size-recs:
	@echo "Linking orders with size recommendations..."
	@./venv/bin/python scripts/link_orders_and_sizes.py || { echo "Missing inputs for size-recs"; exit 1; }
	@./venv/bin/python -c "import pandas as pd, sys; from pathlib import Path as P; fp=P('data_crm/orders_kaspi_with_sizes.xlsx'); (print('missing data_crm/orders_kaspi_with_sizes.xlsx') or sys.exit(1)) if not fp.exists() else None; df=pd.read_excel(fp); df.columns=[str(c).strip().lower().replace(' ','_') for c in df.columns]; subset=df[df['sku_key'].astype(str).str.len().gt(0) & df['rec_size'].astype(str).str.len().gt(0)]; print(subset.head(20).to_csv(index=False)); null_rate=1.0 - (df['rec_size'].astype(str).str.len().gt(0).mean()); (print(f'ERROR: rec_size null-rate {null_rate:.1%} exceeds 10%') or sys.exit(2)) if null_rate>0.10 else None"

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

.PHONY: serve

serve:
	@echo "Starting webhook stub service on http://127.0.0.1:3801 ..."
	@./venv/bin/uvicorn services.api_server:app --reload --port 3801

.PHONY: outbox

outbox:
	@./venv/bin/python scripts/crm_outbox_pack.py --date "$(DATE)"

.PHONY: group-labels

group-labels:
	@test -n "$(INPUT)" || (echo "INPUT=/abs/path/to/waybill.zip required" && exit 2)
	@test -n "$(OUT_DATE)" || (echo "OUT_DATE=YYYY-MM-DD required" && exit 2)
	@echo "Grouping Kaspi label PDFs..."
	@./venv/bin/python scripts/crm_kaspi_labels_group.py --input "$(INPUT)" --out-date "$(OUT_DATE)" --verbose
	@man=$$(ls -t data_crm/labels_grouped/*/manifest.csv 2>/dev/null | head -n1); \
		if [ -f "$$man" ]; then echo "--- manifest preview (first 30 rows) ---"; tail -n +2 "$$man" | head -n 30; else echo "manifest.csv not found"; fi

.PHONY: run-all

run-all:
	INPUT_LABELS="$(INPUT)" OUT_DATE="$(OUT_DATE)" ./scripts/run_e2e.sh

.PHONY: ci-sanity

ci-sanity:
	@./venv/bin/python scripts/ci_sanity.py --strict

.PHONY: waybills

waybills:
	@./venv/bin/python scripts/kaspi_waybills_download.py --date "$(DATE)"
