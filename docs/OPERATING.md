## Schedule

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


