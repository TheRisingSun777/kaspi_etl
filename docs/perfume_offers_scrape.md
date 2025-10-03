# Perfume Offers Scraper

The `scripts/scrape_kaspi_offers.ts` batch scraper reuses the Playwright selectors from `apps/kaspi_offers_dashboard` to fetch seller offers for large product lists.

## Setup

```bash
pnpm install
npx playwright install --with-deps chromium
```

## Usage

```bash
# dry run (first 10 items)
pnpm scrape:perfumes --start 0 --limit 10 --out data_raw/perfumes/offers_smoke.csv

# full run
pnpm scrape:perfumes --out data_raw/perfumes/offers_full.csv
```

Key flags:

- `--input` – path to source XLSX/CSV (defaults to the perfume workbook).
- `--in-col` – override column name when auto-detect fails.
- `--city` – Kaspi `cityId` (defaults to Astana `710000000`).
- `--concurrency` – concurrent pages (default 100, hard cap 100 with adaptive 30→60→100 ramp/backoff).
- `--headless/--no-headless` – toggle Playwright headless mode.
- `--start / --limit` – window over the input list.
- `--out` – output CSV path (auto `data_raw/perfumes/offers_<ts>.csv`).

The script streams both CSV rows and NDJSON logs to `data_raw/perfumes/`. CSV rows are written as:

```
product_code,seller_name,price_kzt,product_url
```

Logs can be used to resume or investigate partial runs.

The CLI maintains `data_raw/perfumes/offers_state.json` so re-running the command automatically fills any skipped indices before continuing from the latest position.

## Known Gotchas

- Sellers are paginated in 5-row pages; the scraper now drains both “Показать ещё” buttons and numeric pagination using DOM change-detection polling.
- The city modal can re-appear mid-pagination; the run enforces cookie + localStorage and clicks “Астана” whenever the chooser resurfaces.

## Troubleshooting

- Backoff only triggers on HTTP 429/503 or the per-product 120 s timeout, and the concurrency floor stays at 50 so we no longer stall at single digits.
- Resume state writes are atomic; if a run is interrupted, delete the state file to restart from scratch.
- Pass `--debug` to watch a headed browser (slowMo 250 ms) for troubleshooting pagination and city selection.
- Debug screenshots for zero-seller pages land in `data_raw/perfumes/debug/`.
- Check `data_raw/perfumes/logs/offers_<ts>.ndjson` for per-product metrics (includes `pagesMeta` and `dupFiltered`).
