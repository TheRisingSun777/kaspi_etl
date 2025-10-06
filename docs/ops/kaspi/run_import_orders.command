#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OPS_ROOT="${SCRIPT_DIR}"
REPO_ROOT="$(cd "${OPS_ROOT}/../../.." && pwd)"
source "${OPS_ROOT}/python_env_bootstrap.zsh"

REQUIREMENTS_FILE="${REPO_ROOT}/requirements.txt"
PYTHON_BIN="$(kaspi_select_python "${REQUIREMENTS_FILE}")"
if [ -z "${PYTHON_BIN}" ]; then
  echo "Unable to initialise Python environment" >&2
  exit 1
fi

ORDERS="${KASPI_ACTIVE_ORDERS_DIR:-${ORDERS:-${OPS_ROOT}/ActiveOrders}}"
WB="${KASPI_CRM_WORKBOOK:-${WB:-${OPS_ROOT}/SALES_KSP_CRM_V3.xlsx}}"
SHEET="${KASPI_CRM_SHEET:-${SHEET:-SALES_KSP_CRM_1}}"
TABLE="${KASPI_CRM_TABLE:-${TABLE:-CRM}}"

echo "🔤 Sorting ActiveOrders by Артикул (A-Z)"
"${PYTHON_BIN}" "${OPS_ROOT}/sort_active_orders.py" --orders-dir "${ORDERS}"

DATE_END="${KASPI_DATE_END:-${DATE_END:-today}}"
STATUS="${KASPI_STATUS:-${STATUS:-Ожидает передачи курьеру}}"
SIGNATURE="${KASPI_SIGNATURE:-${SIGNATURE:-Не требуется}}"
APPEND_DATE="${KASPI_APPEND_DATE:-${APPEND_DATE:-today}}"

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
  --signature "${SIGNATURE}" \
  --append-date "${APPEND_DATE}"

echo "✅ Finished. Open Excel to review when you want."
echo "📦 Check archive_orders for moved exports and appended_orders.csv logs."
