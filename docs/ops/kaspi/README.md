# Kaspi Ops Toolkit

This folder contains the standalone Kaspi automation suite that was migrated into
`kaspi_etl`. It includes two Python entry points and shell wrappers for running
the common flows from the command line.

## Python entry points

- **build_kaspi_orders.py** – bundles waybill ZIP exports and the daily Excel
  order snapshot into per-store PDF manifests. Defaults draw from:
  - `KASPI_INPUT_DIR` (fallback: `Kaspi_orders/input` inside this folder)
  - `KASPI_OUTBASE_DIR` (fallback: `Kaspi_orders`)
  - optional: `KASPI_RUN_DATE`, `KASPI_ZIP_MODE`
- **import_active_orders.py** – appends filtered ActiveOrders exports into the
  CRM workbook via Excel automation. Defaults draw from:
  - `KASPI_ACTIVE_ORDERS_DIR` (fallback: `ActiveOrders`)
  - `KASPI_CRM_WORKBOOK` (fallback: `SALES_KSP_CRM_V3.xlsx`)
  - `KASPI_CRM_SHEET`, `KASPI_CRM_TABLE`, `KASPI_STATUS`, `KASPI_SIGNATURE`

Run either script directly with `python3` or supply explicit arguments to
override the environment-based defaults. Example:

```bash
python3 docs/ops/kaspi/build_kaspi_orders.py \
  --input /path/to/input \
  --outbase /path/to/output \
  --date 2025-09-24
```

## Shell helpers

- `run_today_and_archive_input.command` – orchestrates a daily build using the
  defaults above, then archives processed input files. Respects the same
  environment variables and falls back to the co-located `Kaspi_orders`
  structure.
- `run_import_orders.command` – wraps the import script for a one-command
  workflow using the default cutoff of “today”.
- `run_import_orders_all_dates.command` – identical to the above, but it keeps
  every order regardless of planned courier date (useful when you want to ship
  tomorrow’s orders early).

All shell helpers automatically prefer the repo’s `venv/bin/python`
interpreter; set `KASPI_PYTHON_BIN` (or `PYTHON_BIN`) if you want to override
the interpreter path.

## Environment configuration

| Variable | Purpose |
| --- | --- |
| `KASPI_INPUT_DIR` | Directory with one `.xlsx` plus waybill ZIPs for bundling |
| `KASPI_OUTBASE_DIR` | Output root containing `Today/` and `Archive/` |
| `KASPI_ACTIVE_ORDERS_DIR` | Folder with ActiveOrders exports |
| `KASPI_CRM_WORKBOOK` | Excel workbook that receives appended rows |
| `KASPI_CRM_SHEET` / `KASPI_CRM_TABLE` | Target sheet and table names |
| `KASPI_STATUS` / `KASPI_SIGNATURE` | Filtering criteria for imports |
| `KASPI_APPEND_DATE` | Date stamped into the CRM `Date` column (default: today) |
| `KASPI_PYTHON_BIN` | Interpreter to run the automation (defaults to `python3`) |
| `KASPI_RUN_DATE` / `KASPI_ZIP_MODE` | Optional overrides when bundling |

All variables are optional; the scripts will use the files bundled in this
folder when overrides are not provided.

## Dependencies

Kaspi tooling relies on pandas, openpyxl, xlwings, and pypdf. They are listed in
the project-level `requirements.txt`. Install (or update) them with:

```bash
python3 -m pip install -r requirements.txt
```

Running the daily bundler requires waybill ZIPs and the matching Excel export in
the input directory. When testing locally you can reuse any of the archived
snapshots under `Kaspi_orders/Archive/input_*`.
