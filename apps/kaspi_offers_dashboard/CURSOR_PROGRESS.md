2025-08-10T12:30Z
- Decision: Implemented robust merchant list fetching per CURSOR_TASK.md. Added debug list route and tolerant array key picking.
- Reason: /pricebot showed empty offers due to cluster-specific response shapes. Acceptance requires banner or items.
- Files: app/api/debug/merchant/list (new), app/api/merchant/offers (enhanced), app/api/pricebot/offers (enhanced), lib/kaspi/client (cookie alias), PricebotPanel mapping.
- Next: Verify acceptance checks with curl; then run dev server and validate UI.


