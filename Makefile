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
	@./venv/bin/python scripts/link_orders_and_sizes.py || { echo "Missing inputs for size-recs"; exit 1; }
	@./venv/bin/python - <<'PY'
import pandas as pd
from pathlib import Path
fp = Path('data_crm/orders_kaspi_with_sizes.xlsx')
if not fp.exists():
    print('missing data_crm/orders_kaspi_with_sizes.xlsx')
    raise SystemExit(1)
df = pd.read_excel(fp)
df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]
subset = df[df['sku_key'].astype(str).str.len().gt(0) & df['rec_size'].astype(str).str.len().gt(0)]
print(subset.head(20).to_csv(index=False))
null_rate = 1.0 - (df['rec_size'].astype(str).str.len().gt(0).mean())
if null_rate > 0.10:
    print(f"ERROR: rec_size null-rate {null_rate:.1%} exceeds 10%")
    raise SystemExit(2)
PY

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
	WA_EMPLOYEE_PHONE="$(PHONE)" ./venv/bin/python scripts/wa_send_outbox.py

.PHONY: group-labels

group-labels:
	@echo "Grouping Kaspi label PDFs by processed sales..."
	@./venv/bin/python scripts/crm_kaspi_labels_group.py --input "$$INPUT" --out-date "$$OUT_DATE"
	@man=$$(ls -t data_crm/labels_grouped/*/manifest.csv 2>/dev/null | head -n1); \
		if [ -f "$$man" ]; then echo "--- manifest preview (first 30 rows) ---"; tail -n +2 "$$man" | head -n 30; else echo "manifest.csv not found"; fi

.PHONY: run-all

run-all:
	INPUT_LABELS="$(INPUT)" OUT_DATE="$(OUT_DATE)" ./scripts/run_e2e.sh
