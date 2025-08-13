## Schedule

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


