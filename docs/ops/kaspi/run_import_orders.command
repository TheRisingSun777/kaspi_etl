#!/bin/zsh
set -euo pipefail

ORDERS="/Users/adil/Downloads/ActiveOrders"            # where ActiveOrders*.xlsx are
WB="/Users/adil/Documents/kaspi/SALES_KSP_CRM_V3.xlsx" # your CRM workbook
SHEET="SALES_KSP_CRM_1"                                 # sheet name with the table
TABLE="CRM"                                             # Excel Table name on that sheet
DATE_END="today"                                        # include rows with handover date <= this
STATUS="Ожидает передачи курьеру"
SIGNATURE="Не требуется"

echo "⏱  Date upper bound: ${DATE_END}"
echo "📥 Orders dir: ${ORDERS}"
echo "📄 Workbook: ${WB} (sheet: ${SHEET}, table: ${TABLE})"
echo "🗃  Archive folder: ${ORDERS}/archive_orders"

# Use your venv's python
/Users/adil/.venvs/kaspi/bin/python "/Users/adil/Documents/kaspi/import_active_orders.py" \
  --orders-dir "${ORDERS}" \
  --out-wb "${WB}" \
  --sheet "${SHEET}" \
  --table "${TABLE}" \
  --date-end "${DATE_END}" \
  --status "${STATUS}" \
  --signature "${SIGNATURE}"

echo "✅ Finished. Open Excel to review when you want."
echo "📦 Check archive_orders for moved exports and appended_orders.csv logs."
