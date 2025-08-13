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

.PHONY: size-recs

size-recs:
	@echo "Linking orders with size recommendations..."
	@./venv/bin/python scripts/link_orders_and_sizes.py
	@python - <<'PY'
import pandas as pd
from pathlib import Path
fp=Path('data_crm/orders_kaspi_with_sizes.xlsx')
if fp.exists():
    df=pd.read_excel(fp)
    print(df.head(20).to_csv(index=False))
else:
    print('missing data_crm/orders_kaspi_with_sizes.xlsx')
PY
