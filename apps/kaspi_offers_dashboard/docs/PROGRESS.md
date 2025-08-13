- 2025-08-12 10:05 UTC — UI-002: Opponents modal loader now reads `items` only and sorts by price; opponents count typing/consistency fixed in store; curl verification steps documented.
- 2025-08-12 10:30 UTC — UI-002: Fixed stores route file path to merchants.json and ensured it returns items; dev server command corrected.
- 2025-08-12 21:45 UTC — OPP-002: Added storefront env cookie support, sec-ch headers, HTML JSON-LD scrape, and optional Playwright fallback; robust seller extraction so modal shows names/prices even if IDs vary.
- 2025-08-12 10:22 UTC — UI-002: Fixed offers route to not hard-stop on missing env and improved cookie file discovery paths.
- 2025-08-11 13:26 UTC — UI stabilization: removed legacy rules table; made /pricebot client-only; added Zustand store; added row enrichment trigger; added CSV apply adapter and endpoint; improved cookie reader; fixed build/runtime.
- 2025-08-11 13:34 UTC — UI-002: Added `/api/pricebot/stores` backed by `server/db/merchants.json`; header made sticky with store selector + import/export bar.
- 2025-08-11 13:52 UTC — UI-002: Persist selected storeId to repo `STATE.json` via debug route; wired Bulk Run in header; fixed lints; build green.
- 2025-08-11 17:58 UTC — Opponents: Switched `/api/pricebot/opponents` to POST JSON with browser headers; added logging and city cookie; wired `/api/pricebot/offers?withOpponents=true` to merge sellers.
- 2025-08-11 13:15 UTC — TEST-001: Added import and opponents route smoke tests; green.
- 2025-08-11 13:12 UTC — TEST-001: Added route smoke tests for /api/pricebot/run (dry + bad_input).
- 2025-08-11 13:08 UTC — TEST-001: Added extra unit test for proposal logic; test suite green.
- 2025-08-11 13:02 UTC — PERF-001: Added X-Perf-ms headers to run/offers and X-Perf-cache to opponents.
- 2025-08-11 12:56 UTC — AUTH-001: Added cookie-status route and login.mjs script; documented steps in OPERATING.md.
- 2025-08-11 12:50 UTC — OPP-002: Opponents robustness — JSON backoff, dedupe+sort, extended selectors, 180s cache, and daily trace logs.
- 2025-08-11 12:42 UTC — SAFE-001: Added shared zod validators for run/bulk/export/settings and unified bad_input error responses.
- 2025-08-11 12:35 UTC — BULK-001: Added bulk apply endpoint and Apply All button in progress modal; records appended for applied items.
- 2025-08-11 12:28 UTC — BULK-001: Added progress polling UI with modal; basic proposals per SKU produced server-side.
- 2025-08-11 12:20 UTC — BULK-001: Added bulk run endpoint with simple job tracking and UI trigger; background processes SKU list into proposals.
- 2025-08-11 12:08 UTC — RUN-001: Added zod validation + apply path for single run; UI confirm modal with Apply; run records appended with applied flag.
- 2025-08-11 11:24 UTC — EXP-001: Export includes merchantId/storeId/cityId columns and uses selected city; Import writes to v2 settings with minPrice/maxPrice/stepKzt.
# PROGRESS

- 2025-08-13 01:00 UTC — CORE-LOOP-001: Adjusted `PricebotPanel` Save to POST `/api/pricebot/settings` (schema-compliant). Confirmed inline table edits persist to `server/db/pricebot.settings.json` v2 and reload correctly. Advanced task to next.
- 2025-08-13 01:10 UTC — CORE-LOOP-002: Offers now default to `withOpponents=false`; route returns `ourPrice`, `active`, `min`, `max`, `step`, `interval` top-level; store requests without opponents by default.
- 2025-08-13 01:20 UTC — CORE-LOOP-003: Run route computes proposals ignoring opponents (using guardrails only); returns `proposals[]` plus backward-compatible `proposal` for single SKU; apply path restricted to single SKU.
- 2025-08-13 01:30 UTC — CORE-LOOP-004: Reworked `scripts/price_watch.ts` to read v2 settings and call `/api/pricebot/run?dry=true` for due SKUs; added usage docs under Watchers.
- 2025-08-13 01:38 UTC — CORE-LOOP-004: Accept env overrides for poll interval and API base; added in-memory last-run tracking to avoid over-triggering; advanced STATE to UI-002.

- 2025-08-11 10:22 UTC — Added repo memory scaffold (OPERATING.md, TASKS.yaml, PROGRESS.md, STATE.json, DECISIONS.md). No app code changed.
- 2025-08-11 10:22 UTC — Defaults set: storeId=30141222, cityId=710000000 (adjust if needed).
- 2025-08-11 10:35 UTC — CORE-001: Unified merchant-aware settings: API `/api/pricebot/settings` accepts GET(req) and POST storeId/merchantId; UI passes `storeId` on saves; run/export/opponents consume `pricebot.settings.json` v2.
- 2025-08-11 10:44 UTC — CORE-001: Fixed typecheck, added `@types/formidable`; export links include `storeId`; cleaned scrape types to remove unnecessary ts-expect-error warnings.
- 2025-08-11 10:48 UTC — CORE-001: Offers endpoint maps v2 settings (minPrice/maxPrice/stepKzt/intervalMin/ignoredOpponents) to UI shape.
- 2025-08-11 10:51 UTC — CORE-001 marked done; moving focus to KPI-001 next per plan.
- 2025-08-11 10:58 UTC — KPI-001: Added `/api/pricebot/stats` and overview tiles in `PricebotPanel`; accepts storeId/merchantId; placeholders for winRate/lastRun.*.
- 2025-08-11 11:04 UTC — KPI-001: Implemented local telemetry storage (`server/db/pricebot.runs.json`); `/stats` now returns lastRunCount/lastRunAvgDelta; single-run records on dry-run.
- 2025-08-11 11:10 UTC — KPI-001: Grey out zero-stock rows and auto-disable Active checkbox when stock=0 per UI notes.
- 2025-08-11 11:16 UTC — UX-001: Opponents modal shows Ignored/You badges and brief Saved tick after toggles.
- 2025-08-11 12:00 UTC — Refactored TASKS.yaml backlog (STK-001, OPP-002, EXP-002, RUN-002, KPI-002, STR-001, AUTH-001, UX-002) and added context-rotation note to OPERATING.md.
-- 2025-08-11 13:08 UTC — TEST-001: Added extra unit test for proposal logic; test suite green.
+- 2025-08-11 13:08 UTC — TEST-001: Added extra unit test for proposal logic; test suite green.
+
+## 2025-08-12 15:50 UTC — Pivot to core repricing loop
+
+After several days of debugging the seller/opponents integration, we paused work on scraping competitors and realigned on the core repricing loop.  Seller counts now remain optional, and the `/api/pricebot/offers` endpoint defaults to `withOpponents=false` so it returns our SKUs without blocking.
+
+We added four tasks to the backlog (`CORE-LOOP-001`–`CORE-LOOP-004`) covering settings persistence, offers retrieval, dry‑run proposals, and a scheduler.  We moved `UI-002` back to the backlog as lower priority and updated `STATE.json` to set `CORE-LOOP-001` as the current task.  This pivot frees us to finish the pricing loop quickly while leaving opponents retrieval as a later enhancement.
*** End Patch
EOF