2025-08-10T12:30Z
- Decision: Implemented robust merchant list fetching per CURSOR_TASK.md. Added debug list route and tolerant array key picking.
- Reason: /pricebot showed empty offers due to cluster-specific response shapes. Acceptance requires banner or items.
- Files: app/api/debug/merchant/list (new), app/api/merchant/offers (enhanced), app/api/pricebot/offers (enhanced), lib/kaspi/client (cookie alias), PricebotPanel mapping.
- Next: Verify acceptance checks with curl; then run dev server and validate UI.

2025-08-10T12:34Z
- Decision: Start dev server on available port. Use port 3001 to avoid conflicts and comply with automatic fallback.
- Command: pnpm exec next dev -p 3001

2025-08-10T14:52Z
- Decision: Merchant list actually returns top-level `data` array. Updated array picker to include `data`.
- Result: `/api/merchant/offers` returns >0 items; `/api/pricebot/offers` returns items merged with settings.

2025-08-10T16:47Z
- Issue: `401` from MC when using API key mode. Adjusted headers to send only `X-Auth-Token` (no Bearer). Still 401 on this endpoint with key; cookie mode may be required for list/count in this environment.
- Action: Keep UI tolerant. Debug endpoints return status in body.

2025-08-10T16:58Z
- Added Phase G scope to CURSOR_TASK.md: pricebot controls, opponents, import/export.
- Installed deps: exceljs, papaparse, formidable, zod, @tanstack/react-table.

2025-08-10T17:08Z
- Implemented settings store `server/db/pricebot.store.ts` with atomic writes.
2025-08-10T17:28Z
- Export: mark route runtime as nodejs; harden source picking; include product page link.
2025-08-10T20:22Z
- Export rows now default min/max to current price when unset; import/export bar and global ignore mounted on page; `available=1` supported in offers API.

2025-08-10T20:30Z
- Added SKU parser `extractProductIdAndVariantFromSku` and `buildShopLink`.
- New endpoints: `/api/merchant/offer/stock?sku`, enhanced `/api/pricebot/opponents` (sku→productId, 3m cache) and `/api/pricebot/offers` (derive productId + shop_link).
- Opponents modal now queries with sku; cache applied server-side.

2025-08-10T20:40Z
- Settings API: added toggle per-seller ignore for a SKU. Store now supports 5 store profiles scaffold and active city helper (future use for top knobs).

2025-08-10T20:55Z
- Multi-store: added `/api/pricebot/stores` and UI `StoreSelector` in header (wired for future store scoping).
- Opponents: unified response shape `{items}` and ensured sorting; modal reads it.
- Offers: derive productId via `shopLink` regex; name prefers masterTitle/title/name; real stock mapping retained.
- Defaults: min/max now default to current price when settings missing/zero.
- Reprice: endpoint can use stored settings (min) when `useSettings` is true; added Run button per row.
- Added settings endpoints: GET/POST /api/pricebot/settings.
- Enhanced /api/pricebot/offers to merge settings and real stock mapping.
- Added /api/pricebot/opponents with JSON first, Playwright fallback behind ENABLE_SCRAPE.
- Added /api/pricebot/export (csv/xlsx) and /api/pricebot/import (csv/xlsx, dryRun).
- UI table now uses @tanstack/react-table with sorting and a text filter, plus export buttons.
- Added cookies login script and npm script `cookies:login` to capture mc-session/mc-sid to merchant.cookie.json.


