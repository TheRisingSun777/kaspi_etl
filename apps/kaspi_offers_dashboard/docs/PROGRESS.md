- 2025-08-11 12:28 UTC — BULK-001: Added progress polling UI with modal; basic proposals per SKU produced server-side.
- 2025-08-11 12:20 UTC — BULK-001: Added bulk run endpoint with simple job tracking and UI trigger; background processes SKU list into proposals.
- 2025-08-11 12:08 UTC — RUN-001: Added zod validation + apply path for single run; UI confirm modal with Apply; run records appended with applied flag.
- 2025-08-11 11:24 UTC — EXP-001: Export includes merchantId/storeId/cityId columns and uses selected city; Import writes to v2 settings with minPrice/maxPrice/stepKzt.
# PROGRESS

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
