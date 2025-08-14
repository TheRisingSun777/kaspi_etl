## Schedule

## Daily 16:30 cutoff workflow

- At 16:30 local time, freeze intake and run the end-to-end pipeline for the day.
- Sequence: orders → join → size‑recs → waybills → group‑labels → outbox

Quick command:

```bash
source venv/bin/activate
OUT_DATE=$(date +%F) INPUT="/abs/path/to/waybill.zip" make run-all
```

Artifacts:
- Orders CSV: `data_crm/orders_api_latest.csv`
- Processed sales: `data_crm/processed_sales_latest.csv`
- Size recommendations: `data_crm/orders_kaspi_with_sizes.xlsx`
- Waybills ZIP (downloaded): `data_crm/inputs/waybill_YYYYMMDD.zip`
- Grouped labels: `data_crm/labels_grouped/${OUT_DATE}/`
- Outbox for WhatsApp send: `outbox/${OUT_DATE}/`

## End-to-end run

To run the full pipeline in one command (orders → join → size-recs → labels → WhatsApp send):

```bash
source venv/bin/activate
OUT_DATE=$(date +%F) make run-all INPUT="/abs/path/to/waybill.zip"
```

Notes:
- Each step checks inputs and skips if up-to-date.
- WhatsApp Cloud API requires env set in `.env.local` (WA_TOKEN, WA_PHONE_NUMBER_ID, WA_TO_EMPLOYEE, WA_TEMPLATE_LABELS).
- For labels grouping, ensure waybills ZIP or folder is available; grouped PDFs and `manifest.csv` will be created under `data_crm/labels_grouped/${OUT_DATE}/`.
- To fetch waybills/ActiveOrders from the Merchant Cabinet using your browser cookies:
  - Ensure you're logged in to `mc.shop.kaspi.kz` in Chrome/Brave/Edge/Firefox.
  - Set `KASPI_WAYBILLS_URL` and/or `KASPI_ACTIVEORDERS_URL` in `.env.local` (URLs from DevTools Network).
  - Run:
    - `make fetch-orders` → updates `data_crm/active_orders_latest.xlsx`
    - `make fetch-waybills` → downloads into `data_crm/inbox/waybills/YYYY-MM-DD/` and extracts into `raw/`
  - If cookie scrape fails: set `KASPI_MERCHANT_COOKIE` in `.env.local` as fallback.

### Merchant downloads path (no API dependency)

Use XLSX export to drive the pipeline when the API is unavailable or rate-limited:

```bash
source venv/bin/activate
make run-from-xlsx OUT_DATE=$(date +%F)
```

This runs: fetch-orders → orders-from-xlsx → join → size-recs → (then you can group-labels and outbox as usual).

## Webhook setup (WhatsApp Cloud API)

1) Run the webhook receiver locally:

```bash
source venv/bin/activate
export WA_VERIFY_TOKEN="choose-a-secret"
make serve-webhook
```

2) In Meta Developers → WhatsApp → Webhooks:
   - Callback URL: `http://your-public-tunnel-or-host:3901/webhooks/whatsapp`
   - Verify Token: copy the value of `WA_VERIFY_TOKEN`
   - Subscribe to message status updates.

3) Receipts will be appended to `data_crm/reports/wa_receipts.jsonl`.

## Troubleshooting

- API 401/403
  - Ensure `.env.local` has valid tokens: `KASPI_TOKEN` (or `X_AUTH_TOKEN`), and for WhatsApp: `WA_TOKEN`, `WA_PHONE_NUMBER_ID`.
  - If WhatsApp returns 401/403: check App and Business verification, permissions, or phone number setup.

- API timeouts
  - Orders ETL uses paging and retries with backoff. Re-run `make orders` with `KASPI_ORDERS_SIZE=10` and a specific `KASPI_ORDERS_STATUS`.

- Mapping gaps (missing sku_key)
  - The join step is tolerant: maps by `(ksp_sku_id, store)` → `(product_master_code, store)` → `ksp_sku_id` → `product_master_code`.
  - Gaps are written to `data_crm/reports/missing_ksp_mapping.csv`; keep this under 5% of orders (`make ci-sanity`).
  - Update `data_crm/mappings/ksp_sku_map_updated.xlsx` to improve coverage and re-run join.

- Waybills download issues (401/403)
  - Update `KASPI_MERCHANT_COOKIE` in `.env.local` from browser DevTools (copy full `Cookie` header).
  - Ensure `KASPI_WAYBILLS_URL` is the exact URL used by "Распечатать все накладные".



This project includes a local daily runner for macOS using a shell script and an example LaunchAgent.

Script:

- `scripts/run_daily.sh`
  - Activates the venv
  - make orders → API JSON/CSV
  - python scripts/api_orders_to_csv.py → stage CSV
  - python scripts/join_api_orders_to_sales.py → processed + stock
  - make size-recs; python scripts/crm_build_picklist.py
  - make pack-pdfs zip-exports
  - Logs to `logs/daily_run_YYYYMMDD.log`

LaunchAgent template (save as `~/Library/LaunchAgents/com.kaspi.etl.daily.plist`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.kaspi.etl.daily</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>cd ~/Docs/kaspi_etl_kaspiapi && ./scripts/run_daily.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>16</integer>
    <key>Minute</key>
    <integer>30</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>~/Docs/kaspi_etl_kaspiapi/logs/launchagent.out</string>
  <key>StandardErrorPath</key>
  <string>~/Docs/kaspi_etl_kaspiapi/logs/launchagent.err</string>
  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
```

Enable:

```bash
launchctl unload ~/Library/LaunchAgents/com.kaspi.etl.daily.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.kaspi.etl.daily.plist
launchctl list | grep kaspi
```


