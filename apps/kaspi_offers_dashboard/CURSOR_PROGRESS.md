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


