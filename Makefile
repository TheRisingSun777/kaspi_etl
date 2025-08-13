.PHONY: ci-sanity

PY ?= ./venv/bin/python

ci-sanity:
	@$(PY) scripts/ci_sanity.py
.PHONY: bundle

bundle:
	./scripts/make_repo_bundle.sh

.PHONY: orders

orders:
	@echo "Running ETL for active orders..."
	@./venv/bin/python scripts/etl_orders_api.py
	@./venv/bin/python scripts/api_orders_to_csv.py
	@./venv/bin/python scripts/join_api_orders_to_sales.py

.PHONY: orders-from-cache

orders-from-cache:
	@INPUT_JSON=$${INPUT_JSON:-$$(ls -t data_crm/api_cache/*.json 2>/dev/null | head -n1)} ; \
	echo "Using $${INPUT_JSON}" ; \
	./venv/bin/python scripts/api_orders_to_csv.py --input "$$INPUT_JSON"

.PHONY: sanity

sanity:
	@echo "Mapping columns:" ; \
	python - <<'PY' ; \
import pandas as pd ; \
x='data_crm/mappings/ksp_sku_map_updated.xlsx' ; \
try: print(pd.read_excel(x,nrows=0).columns.tolist()) ; \
except Exception as e: print('missing', x, e) ; \
PY
	@echo "--- orders_api_latest.csv (first 3)" ; head -n 3 data_crm/orders_api_latest.csv || true

.PHONY: group-labels

group-labels:
	@echo "Grouping Kaspi label PDFs by SKU and size..."
	@./venv/bin/python scripts/crm_kaspi_labels_group.py --input "$(INPUT)" $(if $(PROCESSED),--processed "$(PROCESSED)") $(if $(OUT_DATE),--out-date "$(OUT_DATE)")
	@man=$$(ls -t data_crm/labels_grouped/*/manifest.csv 2>/dev/null | head -n1); \
		if [ -f "$$man" ]; then echo "--- manifest preview (first 30 rows) ---"; tail -n +2 "$$man" | head -n 30; else echo "manifest.csv not found"; fi

.PHONY: size-recs

size-recs:
	@echo "Linking orders with size recommendations..."
	@./venv/bin/python scripts/link_orders_and_sizes.py
	@$(PY) -c "import pandas as pd, pathlib as P; fp=P.Path('data_crm/orders_kaspi_with_sizes.xlsx'); print(pd.read_excel(fp).head(20).to_csv(index=False)) if fp.exists() else print('missing data_crm/orders_kaspi_with_sizes.xlsx')"

.PHONY: outbox

outbox:
	@OUT_DATE=$${OUT_DATE:-$$(date +%F)}; \
	./venv/bin/python scripts/outbox_pack.py --out-date "$$OUT_DATE"; \
	if [ "$$(uname)" = "Darwin" ]; then open "outbox/$$OUT_DATE"; fi

.PHONY: fetch-waybills

fetch-waybills:
	@./venv/bin/python scripts/fetch_waybills_mc.py $(foreach s,$(STATUS),--status $(s)) --out-date "$(OUT_DATE)"

.PHONY: wa-open

wa-open:
	@osascript scripts/wa_open_chat.scpt "$(PHONE)"
