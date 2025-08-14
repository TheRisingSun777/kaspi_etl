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
	@python - <<'PY'
import os, sys, time
from datetime import datetime, timezone
import pytz
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
tz = pytz.timezone('Asia/Almaty')
now = datetime.now(tz)
start = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=tz)
end = datetime(now.year, now.month, now.day, 23, 59, 59, tzinfo=tz)
ms = lambda d: int(d.timestamp() * 1000)
base = os.environ.get('KASPI_ACTIVEORDERS_URL', '').strip().strip('"').strip("'")
if not base:
    print('Missing KASPI_ACTIVEORDERS_URL'); sys.exit(2)
u = urlparse(base)
qs = parse_qs(u.query)
qs['fromDate'] = [str(ms(start))]
qs['toDate'] = [str(ms(end))]
new_q = urlencode(qs, doseq=True)
new_url = urlunparse((u.scheme or 'https', u.netloc, u.path, u.params, new_q, u.fragment))
os.execvp('make', ['make', 'fetch-orders', f'URL={new_url}'])
PY

fetch-waybills-today:
	@python - <<'PY'
import os, sys
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
base = os.environ.get('KASPI_WAYBILLS_URL', '').strip().strip('"').strip("'")
if not base:
    print('Missing KASPI_WAYBILLS_URL'); sys.exit(2)
u = urlparse(base)
qs = parse_qs(u.query)
# keep as-is; sometimes not date-bound
new_q = urlencode(qs, doseq=True)
new_url = urlunparse((u.scheme or 'https', u.netloc, u.path, u.params, new_q, u.fragment))
os.execvp('make', ['make', 'fetch-waybills', f'URL={new_url}'])
PY