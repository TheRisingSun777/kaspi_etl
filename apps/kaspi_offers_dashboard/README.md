# Kaspi Offers Insight (Next.js + TypeScript + Tailwind)

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
pnpm dev
```
Open `http://localhost:3000`.

## Notes
- The server acquires public seller data from product pages/endpoints; token is used only for product name via merchant API.
- If endpoints change, `app/api/analyze/route.ts` is written defensively with fallbacks.


