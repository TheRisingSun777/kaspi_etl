# Pricebot Spec (v2)
- Data model v2 persisted in `server/db/pricebot.json` keyed by `storeId`.
- Endpoints: `/api/pricebot/offers`, `/api/pricebot/opponents`, `/api/pricebot/settings`, `/api/pricebot/export`, `/api/pricebot/import`, `/api/pricebot/run`.
- UI: store selector, global ignore, searchable/sortable table, opponents modal with ignore toggles, import/export, per-row run.
0) Non‑negotiables
	•	Auth split
	•	Use MC (merchant cabinet) cookie for listing offers, stock and price updates.
	•	Use Shop API (+ X‑Auth‑Token) for product classification, product import, and orders/v2 flows.
	•	Persistence in apps/kaspi_offers_dashboard/server/db/pricebot.json. Never rely only on client state.
	•	City – respect NEXT_PUBLIC_DEFAULT_CITY_ID / per‑store override.

1) Data model (server/db/pricebot.json)
{
  "stores": [
    {
      "merchantId": "30141222",
      "label": "Store #1",
      "authMode": "cookie",
      "cityId": 710000000,
      "cookieFile": "server/db/merchant.30141222.cookie.json",
      "apiKey": ""
    }
    /* +4 more stores */
  ],
  "globalIgnore": ["12345678","87654321"],
  "items": [
    {
      "merchantId": "30141222",
      "sku": "CL_OC_MEN_PRINT51_BLACK_116155651_44-46_(M)",
      "productId": "116155651",
      "active": true,
      "min": 8600,
      "max": 9000,
      "step": 1,
      "intervalMin": 5,
      "opponentsIgnore": ["11111111","22222222"],
      "lastRunAt": "2025-08-10T10:12:00Z",
      "lastResult": { "newPrice": 8612, "reason": "beat next by 1 KZT" }
    }
  ]
}
2) Server routes (Next.js app router)
	•	GET /api/pricebot/stores → list stores from pricebot.json.
	•	POST /api/pricebot/stores → add/update store (label, cityId, apiKey, cookie file path).
	•	GET /api/pricebot/offers?merchantId=&cityId=&q=
	•	Returns live offers for the selected store; must include our current price and our real stock.
	•	GET /api/pricebot/opponents?productId=&cityId=
	•	Returns the current seller list (merchantId, sellerName, price, isFBS/FBO, rating if available).
	•	POST /api/pricebot/run (body: { merchantId, sku })
	•	Re-price a single line item immediately (uses settings & ignores).
	•	POST /api/pricebot/bulk/run (body: { merchantId, skus: [] })
	•	Re-price a subset (or all active: true).
	•	GET /api/pricebot/export?format=csv|xlsx
	•	POST /api/pricebot/import (multipart)
	•	Validates, previews diffs, then applies to pricebot.json.
	•	GET/POST /api/pricebot/settings
	•	Whole‑file get/set with zod validation.

Notes based on your current UI: the header already has Export/Upload and “Global ignore merchant IDs” controls, and the table shows Active/Min/Max/Step/Interval/Opponents. We only need to wire them to these endpoints and persist correctly.  ￼

3) Cookie automation (no more manual copy/paste)
	•	Add server/lib/mcCookieStore.ts:
	•	getCookies(merchantId) → reads merchant.{id}.cookie.json.
	•	refreshCookies(merchantId) → Playwright login flow using KASPI_USER/KASPI_PASS from .env.local and optional 2FA; store to file.
	•	Auto‑refresh on 401 and nightly at 03:00 local.
	•	Add CLI script: pnpm mc:login --store 30141222 → triggers refreshCookies with a visible browser first run (headful), then headless.

4) Multi‑store header
	•	Add a segmented control at the top: Store #1 … Store #5.
	•	Changing store reloads offers via GET /api/pricebot/offers?merchantId=....
	•	Persist last selected store in localStorage and include its label in the title (“Pricebot (Store 30141222)”). Current title matches the single store snapshot.  ￼

5) Opponents modal
	•	Clicking the number in “Opponents” opens a medium modal:
	•	Table: Seller, Merchant ID (copy icon), Price, Fulfillment, Rating, Toggle Exclude (per product).
	•	“Exclude all by default” switch; per‑seller overrides.
	•	Save writes opponentsIgnore into items[].
	•	The count in the main table = # of live sellers (not excluded).

6) Sorting, filtering, UX
	•	Use @tanstack/react-table for sorting on every column, and add column filters (min/max price ranges, only Active, etc.).
	•	“Filter by text…” already exists near the right—keep that as global filter.  ￼

7) Import/Export schema (CSV/XLSX)

Columns (exact order):
SKU, model, brand, price, PP1, preorder, min_price, max_price, step, interval_min, shop_link, pricebot_status
	•	pricebot_status: on|off → maps to active: true|false.
	•	On import: validate with zod, show preview, then merge into items[] by SKU.
	•	On export: include current settings + derived shop_link (you already make SKU a link to kaspi.kz in the table).  ￼

8) Repricing engine (server)
	•	For each active SKU on a timer:
	1.	Fetch opponents list for that productId & city.
	2.	Remove globalIgnore and the SKU’s opponentsIgnore.
	3.	Compute target price:
	•	If no competitors → clamp to [min,max]; else min(max( (lowestCompetitor - step), min ), max).
	•	Don’t change if within step of current price (hysteresis).
	4.	If changed → update via MC endpoint; log to server/db/pricebot.log.jsonl.
	•	Manual Run button triggers (3) for a single row.

9) Metrics (top bar)
	•	“Active SKUs”, “Price changes (24h)”, “Median competitor gap”, “% at floor/ceiling”, “Est. margin @ target” (if COGS provided).
	•	Later: Buy‑box share proxy, time‑to‑sell forecasts.

10) Styling & micro‑interactions
	•	Tailwind + shadcn/ui + Radix primitives.
	•	Micro‑anims via framer-motion:
	•	Smooth toggle animation on “Active”.
	•	Modal scale/fade for Opponents.
	•	Subtle row highlight on autosave.
	•	“Premium” surface: soft gradient header, subtle glass card for the table header, San‑serif font pairing, consistent 12/16pt spacing. The current table layout is close—just needs the skinning + motion.  ￼

11) Acceptance Criteria
	•	Stock shows real numbers from MC for each SKU (no more all “1”).  ￼
	•	Clicking an Opponents count opens the modal with real sellers and working exclude toggles.
	•	Per‑row Active/Min/Max/Step/Interval persist and are respected by both Run and the scheduler.
	•	Import/Export round‑trips with the exact schema above.
	•	Top segmented control switches between 5 stores, each with its own auth and cityId.
	•	Basic metrics render and react to filters.
	•	No manual cookie pasting needed after first headful login; cookies auto‑refresh.