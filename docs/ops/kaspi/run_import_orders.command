#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OPS_ROOT="${SCRIPT_DIR}"

ORDERS="${KASPI_ACTIVE_ORDERS_DIR:-${ORDERS:-${OPS_ROOT}/ActiveOrders}}"
WB="${KASPI_CRM_WORKBOOK:-${WB:-${OPS_ROOT}/SALES_KSP_CRM_V3.xlsx}}"
SHEET="${KASPI_CRM_SHEET:-${SHEET:-SALES_KSP_CRM_1}}"
TABLE="${KASPI_CRM_TABLE:-${TABLE:-CRM}}"
DATE_END="${KASPI_DATE_END:-${DATE_END:-today}}"
STATUS="${KASPI_STATUS:-${STATUS:-Ожидает передачи курьеру}}"
SIGNATURE="${KASPI_SIGNATURE:-${SIGNATURE:-Не требуется}}"
PYTHON_BIN="${KASPI_PYTHON_BIN:-${PYTHON_BIN:-python3}}"

echo "⏱  Date upper bound: ${DATE_END}"
echo "📥 Orders dir: ${ORDERS}"
echo "📄 Workbook: ${WB} (sheet: ${SHEET}, table: ${TABLE})"
echo "🗃  Archive folder: ${ORDERS}/archive_orders"

"${PYTHON_BIN}" "${OPS_ROOT}/import_active_orders.py" \
  --orders-dir "${ORDERS}" \
  --out-wb "${WB}" \
  --sheet "${SHEET}" \
  --table "${TABLE}" \
  --date-end "${DATE_END}" \
  --status "${STATUS}" \
  --signature "${SIGNATURE}"

echo "✅ Finished. Open Excel to review when you want."
echo "📦 Check archive_orders for moved exports and appended_orders.csv logs."
