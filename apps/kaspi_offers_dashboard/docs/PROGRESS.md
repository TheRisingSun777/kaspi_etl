# PROGRESS

- 2025-08-11 10:22 UTC — Added repo memory scaffold (OPERATING.md, TASKS.yaml, PROGRESS.md, STATE.json, DECISIONS.md). No app code changed.
- 2025-08-11 10:22 UTC — Defaults set: storeId=30141222, cityId=710000000 (adjust if needed).
- 2025-08-11 10:35 UTC — CORE-001: Unified merchant-aware settings: API `/api/pricebot/settings` accepts GET(req) and POST storeId/merchantId; UI passes `storeId` on saves; run/export/opponents consume `pricebot.settings.json` v2.
- 2025-08-11 10:44 UTC — CORE-001: Fixed typecheck, added `@types/formidable`; export links include `storeId`; cleaned scrape types to remove unnecessary ts-expect-error warnings.
