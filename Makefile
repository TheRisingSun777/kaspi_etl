PY?=$(shell [ -x venv/bin/python ] && echo venv/bin/python || which python3)

.PHONY: orders fetch-orders fetch-waybills fetch-all orders-from-xlsx join size-recs group-labels outbox wa-send run-all run-from-xlsx
.PHONY: fetch-orders-today fetch-waybills-today

orders:
	@echo "orders: starting..."
	@$(PY) scripts/etl_orders_api.py
	@echo "orders: ok"

fetch-orders:
	@echo "fetch-orders: starting..."
	@$(PY) scripts/mc_fetch.py --orders
	@echo "fetch-orders: ok"

fetch-waybills:
	@echo "fetch-waybills: starting..."
	@$(PY) scripts/mc_fetch.py --waybills
	@echo "fetch-waybills: ok"

fetch-all: fetch-orders fetch-waybills
	@echo "fetch-all: ok"

orders-from-xlsx:
	@echo "orders-from-xlsx: starting..."
	@$(PY) scripts/etl_orders_xlsx.py
	@echo "orders-from-xlsx: ok"

join:
	@echo "join: starting..."
	@$(PY) scripts/join_api_orders_to_sales.py
	@echo "join: ok"

size-recs:
	@echo "size-recs: starting..."
	@$(PY) scripts/link_orders_and_sizes.py
	@echo "size-recs: ok"

group-labels:
	@test -n "$(OUT_DATE)" || (echo "OUT_DATE=YYYY-MM-DD required" && exit 2)
	@echo "group-labels: starting..."
	@$(PY) scripts/crm_kaspi_labels_group.py --input "$(INPUT)" --out-date "$(OUT_DATE)" --verbose
	@echo "group-labels: ok"

outbox:
	@test -n "$(OUT_DATE)" || (echo "OUT_DATE=YYYY-MM-DD required" && exit 2)
	@echo "outbox: starting..."
	@$(PY) scripts/crm_outbox_pack.py --date "$(OUT_DATE)"
	@echo "outbox: ok"

wa-send:
	@test -n "$(OUT_DATE)" || (echo "OUT_DATE=YYYY-MM-DD required" && exit 2)
	@echo "wa-send: starting..."
	@$(PY) scripts/wa_send_outbox_waba.py --date "$(OUT_DATE)"
	@echo "wa-send: ok"

run-all: orders join size-recs group-labels wa-send
	@echo "run-all: ok"

run-from-xlsx: fetch-orders orders-from-xlsx join size-recs
	@echo "run-from-xlsx: ok"

.PHONY: run-from-xlsx-today

run-from-xlsx-today:
	@$(MAKE) fetch-orders-today
	@$(MAKE) orders-from-xlsx
	@$(MAKE) join
	@$(MAKE) size-recs
	@zip=$$(ls -t data_crm/inbox/waybills/*/*.zip 2>/dev/null | head -n1); \
		out=$$(date +%F); \
		if [ -n "$$zip" ]; then $(MAKE) group-labels INPUT="$$zip" OUT_DATE="$$out"; else echo "No waybills zip found"; fi
	@$(MAKE) outbox DATE=$$(date +%F)
	@echo "run-from-xlsx-today: ok"

fetch-orders-today:
	@url=$$($(PY) scripts/mc_url_today.py orders); \
		if [ -z "$$url" ]; then echo "https://mc.shop.kaspi.kz/order/view/mc/order/export?presetFilter=KASPI_DELIVERY_WAIT_FOR_COURIER&merchantId=30141222&fromDate=1755111600000&toDate=1755198000000&archivedOrderStatusFilter=RETURNING%2CRETURNED&_m=30141222"; exit 2; fi; \
		$(MAKE) fetch-orders URL="$$url"

fetch-waybills-today:
	@url=$$($(PY) scripts/mc_url_today.py waybills); \
		if [ -z "$$url" ]; then echo "https://mc.shop.kaspi.kz/merchantcabinet/api/order/downloadWaybills?...&_m=30141222"; exit 2; fi; \
		$(MAKE) fetch-waybills URL="$$url"