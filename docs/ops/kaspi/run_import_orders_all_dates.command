#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OPS_ROOT="${SCRIPT_DIR}"
REPO_ROOT="$(cd "${OPS_ROOT}/../../.." && pwd)"
VENV_PYTHON="${REPO_ROOT}/venv/bin/python"

if [ -x "${VENV_PYTHON}" ]; then
  DEFAULT_PYTHON="${VENV_PYTHON}"
else
  DEFAULT_PYTHON="$(command -v python3 || true)"
fi

if [ -z "${DEFAULT_PYTHON}" ]; then
  echo "Unable to locate a python interpreter. Set KASPI_PYTHON_BIN to a valid executable." >&2
  exit 1
fi

PYTHON_BIN="${KASPI_PYTHON_BIN:-${PYTHON_BIN:-${DEFAULT_PYTHON}}}"

ORDERS="${KASPI_ACTIVE_ORDERS_DIR:-${ORDERS:-${OPS_ROOT}/ActiveOrders}}"
WB="${KASPI_CRM_WORKBOOK:-${WB:-${OPS_ROOT}/SALES_KSP_CRM_V3.xlsx}}"
SHEET="${KASPI_CRM_SHEET:-${SHEET:-SALES_KSP_CRM_1}}"
TABLE="${KASPI_CRM_TABLE:-${TABLE:-CRM}}"

# Step 1: sort all ActiveOrders exports by SKU for consistent review
if [ "${KASPI_SKIP_SORT:-0}" != "1" ]; then
  echo "🔤 Sorting ActiveOrders by Артикул (A-Z)"
  "${PYTHON_BIN}" "${OPS_ROOT}/sort_active_orders.py" --orders-dir "${ORDERS}"
fi

# Use a far-future end date to keep every order regardless of planned day
DATE_END="${KASPI_DATE_END:-${DATE_END:-9999-12-31}}"
STATUS="${KASPI_STATUS:-${STATUS:-Ожидает передачи курьеру}}"
SIGNATURE="${KASPI_SIGNATURE:-${SIGNATURE:-Не требуется}}"
APPEND_DATE="${KASPI_APPEND_DATE:-${APPEND_DATE:-today}}"

echo "🚚 Importing with no date cutoff (date_end = ${DATE_END})"
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

echo "✅ Finished. All ActiveOrders (any planned date) have been appended."
echo "📦 Check archive_orders for moved exports and appended_orders.csv logs."
