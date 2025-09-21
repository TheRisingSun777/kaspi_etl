# DECISIONS

## 2025-08-11 — Repo-based memory vs chat memory
We persist operating rules, tasks, progress, and state in the repo to avoid context-window loss and make work resumable. Chat stays minimal; the repo is the single source of truth.

## 2025-08-11 — Merchant-aware scoping (merchantId + storeId + cityId)
All caches and routes are keyed by merchant/store/city (and product where relevant) so multiple merchants/stores can run side by side without collisions.

## 2025-08-11 — Settings source of truth migration to v2
We standardized on `server/db/pricebot.settings.json` keyed by merchantId. UI writes via `/api/pricebot/settings` with `storeId` as merchantId; routes (opponents/run/export) now read v2 fields (minPrice/maxPrice/stepKzt/ignoredOpponents). Legacy `pricebot.json` helpers remain for backward compatibility but are not used for new writes.

## 2025-08-11 — Stores source list from repo file
We expose `/api/pricebot/stores` backed by `server/db/merchants.json` to avoid coupling to env vars and to keep store metadata (ids, labels) editable without code changes. The UI only needs id/name and persists the chosen id in localStorage, which also aligns with repo memory in `STATE.json` later.

## 2025-08-11 — Local telemetry for KPIs (runs)
We persist lightweight run telemetry to `server/db/pricebot.runs.json` keyed by merchantId to power KPI tiles (`/api/pricebot/stats`). Each run stores timestamp, count, and avgDelta. This avoids DB complexity and keeps privacy local. Future: aggregate bulk runs and compute winRate once apply-path is implemented.

## 2025-08-11 — Dry-run by default for repricing
All run/bulk actions default to dry-run and require explicit confirmation to apply, to prevent accidental price changes.

## 2025-08-12 — Opponents API response shape normalization
Kaspi intermittently returns sellers as a top-level array or under `items`. The UI `OpponentsModal` now reads `items` only, while the server route always normalizes and returns `{ ok, items: [...] }`. This avoids coupling the modal to legacy `{ sellers: [] }` shapes and reduces UI branching. Store opponents count also tolerates either a numeric `opponents` or a `sellers[]` list.

## 2025-08-11 — Import validation with zod + preview
Imports are validated first; errors are typed and shown as toasts. No mutation occurs until the user confirms a clean import.

## 2025-08-11 — Conventional commits and small diffs
We keep commits small and descriptive (Conventional Commits) to simplify reviews and bisects in production.
## 2025-08-12 — Pivot to core repricing loop; opponents optional
After spending several days chasing seller counts, we decided to prioritise the core repricing loop and treat opponents (seller) data as an enhancement rather than a blocker.  The core tasks are:

1. Verify settings persistence so that min/max/step/interval changes are saved to `server/db/pricebot.settings.json` and loaded back into the UI.
2. Return offers without opponents by default. The offers API should return our SKUs with price/stock even if opponents are unavailable.
3. Implement run proposals ignoring opponents when necessary and clamp target prices within the `[min,max]` range using the configured step.
4. Introduce a price watch script to call `/run` on a schedule, computing proposals for SKUs whose interval has elapsed.

Opponents retrieval (seller lists) is behind a flag and a cache; it should not block or crash the app. Seller scraping may be implemented later via HTML parsing or Playwright fallback, but the main loop must function without it. We added new tasks `CORE-LOOP-001` to `CORE-LOOP-004` to the backlog to cover these core steps and moved `UI-002` back to backlog. `STATE.json` reflects `lastSeen.taskId` as `CORE-LOOP-001`.
*** End Patch
EOF