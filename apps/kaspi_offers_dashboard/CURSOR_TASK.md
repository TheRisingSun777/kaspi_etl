API Reference: Use apps/kaspi_offers_dashboard/docs/KASPI_API_GUIDE.md as the single source of truth for all Kaspi endpoints, auth, and payloads. Do not browse; if something is ambiguous, choose the safest shippable default and log it to CURSOR_PROGRESS.md.

# Kaspi Offers Insight — Pricebot (Phase G Full Feature Pass)

## Source of truth
- This file is the only spec to follow. Do not stop until every Acceptance Criterion below is ✅.
- Log every decision and progress to `apps/kaspi_offers_dashboard/CURSOR_PROGRESS.md`.
- Work in **small commits**. No secrets in git. Respect `.env.local` and `.gitignore`.

## Environment (do not change in code)
- Listing + repricing use **Merchant Cabinet** base:
  - `KASPI_MERCHANT_API_BASE=https://mc.shop.kaspi.kz`
  - Cookie auth (preferred): `KASPI_MERCHANT_COOKIES=mc-session=...; mc-sid=...`
- API key may exist in `.env.local` but is not required for Phase G.
- Default city to show opponents/pricing examples: `CITY_ID` or `NEXT_PUBLIC_DEFAULT_CITY_ID` = `710000000`.

## Data model (settings store)
Create/maintain `apps/kaspi_offers_dashboard/server/db/pricebot.json` (gitignored) shaped as:
```json
{
  "global": {
    "cityId": "710000000",
    "ignoreSellers": ["<merchantId1>", "<merchantId2>"]
  },
  "items": {
    "SKU_A": {
      "active": true,
      "min": 8000,
      "max": 12000,
      "step": 50,
      "interval": 5,
      "ignoreSellers": ["<merchantIdX>"]
    }
  },
  "updatedAt": "2025-01-01T00:00:00.000Z"
}
	•	active toggles pricebot per SKU.
	•	interval in minutes (1..15).
	•	Per-SKU ignoreSellers augments (does not replace) global.ignoreSellers.

Server endpoints (create/update)

All endpoints live in apps/kaspi_offers_dashboard/app/api/... (Next.js route handlers):
	1.	GET /api/merchant/offers?p=&l=&available=1
	•	Call MC list (cookie auth).
	•	Normalize to:type MerchantOffer = {
  sku: string
  productId: number | null
  name: string
  price: number
  stock: number // real stock (NOT hard-coded 1)
}
	•	Stock mapping: detect one of: quantity, availableQuantity, available, stock. Fallback to 0 if unknown. Include robust “picker” against data, items, content, etc.

	2.	GET /api/pricebot/offers
	•	Merge merchant offers with settings to:
   type PricebotItem = MerchantOffer & {
  opponents: number // can be 0 if not fetched yet
  settings: {
    active: boolean
    min: number
    max: number
    step: number
    interval: number
    ignoreSellers: string[]
  }
}
	•	If settings missing for a SKU, return defaults: {active:false,min:0,max:0,step:1,interval:5,ignoreSellers:[]}.

	3.	GET /api/pricebot/settings
	•	Returns the full settings JSON.
	4.	POST /api/pricebot/settings
	•	Body supports:
	•	Update global: { global: { cityId?: string, ignoreSellers?: string[] } }
	•	Update per SKU batch:
   {
  "items": {
    "SKU_A": {"active":true,"min":8000,"max":12000,"step":50,"interval":5,"ignoreSellers":["123"]}
  }
}
•	Merge + atomic write (write temp then rename).

	5.	GET /api/pricebot/opponents?productId=...&cityId=...
	•	Return:
   type Opponent = {
  merchantId: string
  name: string
  price: number
  isSelf: boolean
}
•	Sorted by price ASC. If productId missing, return {ok:true, items: []}.
	•	Implementation:
	•	Primary: Playwright scrape (feature-flagged). Use persistent context and fetch the product page https://kaspi.kz/shop/p/{productId}/?cityId=...#offers, then parse DOM or XHR to build sellers + prices.
	•	Env flag: ENABLE_SCRAPE=1.
	•	If flag is off or scrape fails, return an empty array (do not crash).

	6.	POST /api/pricebot/reprice
	•	Already exists; keep hitting MC .../price/trends/api/v1/mc/discount with payload:
   { merchantUID, merchantSKU, entries: [{city, price}] }
   •	Return MC response. Do not change this route contract.

	7.	Export/Import:
	•	GET /api/pricebot/export?format=csv|xlsx
	•	Build rows with header exactly:
   SKU,model,brand,price,PP1,preorder,min_price,max_price,step,shop_link,pricebot_status
   •	model, brand, PP1, preorder can be empty for now.
	•	shop_link: if productId known → https://kaspi.kz/shop/p/{productId}?cityId={city}, else search URL https://kaspi.kz/shop/search/?text={encodeURIComponent(sku)}

	•	POST /api/pricebot/import (multipart)
	•	Accept CSV or XLSX.
	•	Parse with papaparse or exceljs. Validate with zod.
	•	Mapping:
	•	Update settings: min_price, max_price, step, pricebot_status → active.
	•	If price differs, trigger POST /api/pricebot/reprice for that SKU (queue sequentially with small delay).

Cookie helper (one-time login, no password in env)
	•	Add script scripts/cookies-login.ts:
	•	Launch Playwright headful persistent context.
	•	Open https://kaspi.kz/.
	•	Instruct user to log in manually.
	•	Poll for cookies mc-session and mc-sid, then save to server/db/merchant.cookie.json:
   {"cookies": "mc-session=...; mc-sid=...", "savedAt": "..."}
   	•	In our MC client, prefer this file if present; otherwise use KASPI_MERCHANT_COOKIES.

UI (Pricebot page)
	•	File(s):
	•	components/pricebot/PricebotTable.tsx
	•	components/pricebot/OpponentsModal.tsx
	•	components/pricebot/GlobalIgnore.tsx
	•	components/pricebot/ImportExportBar.tsx
	•	Use @tanstack/react-table for sorting & column filters.
	•	Columns:
	1.	Active (toggle) → updates settings (debounced save)
	2.	Name (fallback from SKU prefix)
	3.	SKU (monospace, clickable link; productId link if known, else search link)
	4.	Variant (parse from SKU suffix in parentheses)
	5.	Our Price (readonly number or editable field only when we support inline reprice later)
	6.	Stock (real stock from API)
	7.	Min / Max / Step / Interval (inputs; interval 1..15; show helper text “min..max KZT; step KZT; run every N min”)
	8.	Opponents (N as a link) → opens modal:
	•	Modal lists sellers sorted asc by price.
	•	Each seller row: name, price, toggle “Ignore”.
	•	Persist per‑SKU ignoreSellers.
	•	Top toolbar:
	•	Global ignore input: comma/space separated merchant IDs → saves to global.ignoreSellers.
	•	Buttons: Export CSV, Export XLSX, Import (accept .csv/.xlsx).
	•	“Reload” button re-fetches /api/pricebot/offers.

Styling
	•	Keep current dark theme but upgrade the look:
	•	Add subtle gradients to page header and cards.
	•	Animate Active toggles (scale/opacity) and modal opening (fade/scale).
	•	Keep it clean, Apple‑ish.

Acceptance Criteria (must be all ✅)
	•	Pricebot table renders real offers with correct stock.
	•	Each row: Active toggle, Min/Max/Step/Interval inputs; debounced save to settings store.
	•	Opponents count clickable → modal with sorted sellers + per‑seller ignore toggles; saved.
	•	Global ignore field updates global.ignoreSellers.
	•	All columns sortable; per‑column filter available.
	•	Export CSV/XLSX with exact header.
	•	Import CSV/XLSX applies settings; if price changed, calls /api/pricebot/reprice.
	•	SKU links to product page (or search page).
	•	No crashes if opponents scrape fails; returns empty list gracefully.
	•	No secrets committed; all JSON db files ignored by git.
	•	Progress log updated.

Commit etiquette
	•	Small commits. Clear messages. Push to feat/offers-dashboard.
	•	Don’t pause to ask questions; pick safe defaults, log them, and continue.
