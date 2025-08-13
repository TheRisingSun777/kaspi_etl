# Kaspi Offers Dashboard + Pricebot (Next.js + TypeScript + Tailwind)

Modern one‑page dashboard to analyze Kaspi master product ID, variants, and sellers.

## Features
- Server API: `POST /api/analyze { masterProductId, cityId? }`
- Tailwind UI, dark mode, responsive
- KPI cards, variant cards, sellers tables
- Export CSV/XLSX, Copy JSON
- LocalStorage keeps last 5 product IDs
- No secrets in client bundle

## Setup
1) Terminal → go to app
```bash
cd /Users/adil/Docs/kaspi_etl/apps/kaspi_offers_dashboard
```
2) Create `.env.local` (server-only)
```bash
cp .env.local.example .env.local
```
Edit `.env.local` and set your `KASPI_TOKEN`.

3) Install deps (Node via Homebrew already installed earlier)
```bash
corepack enable
corepack prepare pnpm@latest --activate
pnpm install
```

4) Run dev server
```bash
PORT=3001 pnpm dev
```
Open `http://localhost:3001`.

## Env vars (core loop)
- DEFAULT_CITY_ID (e.g. 710000000)
- NEXT_PUBLIC_DEFAULT_CITY_ID
- KASPI_MERCHANT_ID (e.g. 30141222)
- KASPI_MERCHANT_COOKIE (mc-session; dev only; do NOT commit)
- KASPI_MERCHANT_API_BASE (default https://mc.shop.kaspi.kz)
- DRY_RUN=true (server will log apply payload instead of sending)
- KASPI_TOKEN (optional, used for product name; never exposed client-side)
- DEBUG_SCRAPE=0|1
- PW_HEADLESS=0|1 (default 1), PW_SLOWMO=0|250

Example `.env.local`:

```
DEFAULT_CITY_ID=710000000
NEXT_PUBLIC_DEFAULT_CITY_ID=710000000
DEBUG_SCRAPE=1
PW_HEADLESS=0
PW_SLOWMO=250
```

## Watch prices (scheduler)
```bash
pnpm tsx apps/kaspi_offers_dashboard/scripts/price_watch.ts --merchantId=30141222 --city=710000000 --pollSec=60
```
Reads settings v2 and calls `/api/pricebot/run?dry=true` for due SKUs by interval.

## Core loop smoke tests (curl)

Offers without opponents:
```bash
curl -sS "http://localhost:3001/api/pricebot/offers?withOpponents=false&storeId=30141222" | jq '.items[0]'
```

Run (dry):
```bash
curl -sS 'http://localhost:3001/api/pricebot/run' \
  -H 'Content-Type: application/json' \
  --data '{"storeId":"30141222","sku":"SKU_HERE","ourPrice":9999,"dry":true}' | jq
```

Run (apply): ensure `KASPI_MERCHANT_COOKIE` is set or `DRY_RUN=true` for safe logs.
```bash
curl -sS 'http://localhost:3001/api/pricebot/run' \
  -H 'Content-Type: application/json' \
  --data '{"storeId":"30141222","sku":"SKU_HERE","ourPrice":9999,"dry":false}' | jq
```

## Metrics
- median, spread=max−min, stddev
- botShare: fraction of sellers flagged `isPriceBot`
- attractivenessIndex: weighted blend of spread ratio vs median, competition penalty, rating boost, and bot penalty
- stabilityScore: 0–100 based on stddev/min
- bestEntryPrice: min of predicted 24h mins if ≥2 bots else current global min

## Heuristics
- Price-bot: near-min by absolute (+0..15 KZT) or relative (+0..0.25%) in tight market (median−min ≤ 30)
- Predictions: if ≥2 bots then min may drop ~20 KZT in 24h (~40 in 7d)

## City codes
- Astana/Nur‑Sultan: 710000000
- Almaty: 750000000
- Shymkent: 620000000

## Notes
- The server acquires public seller data from product pages/endpoints; token is used only for product name via merchant API.
- If endpoints change, `app/api/analyze/route.ts` is written defensively with fallbacks.
- Use DEBUG_SCRAPE=1 to capture HTML/screenshots to `data_raw/debug/` for unresolved cases
- Respect small concurrency (1–2 pages), random jitter; keep per‑master runtime under ~2 minutes


