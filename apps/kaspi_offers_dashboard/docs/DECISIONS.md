# DECISIONS

## 2025-08-11 — Repo-based memory vs chat memory
We persist operating rules, tasks, progress, and state in the repo to avoid context-window loss and make work resumable. Chat stays minimal; the repo is the single source of truth.

## 2025-08-11 — Merchant-aware scoping (merchantId + storeId + cityId)
All caches and routes are keyed by merchant/store/city (and product where relevant) so multiple merchants/stores can run side by side without collisions.

## 2025-08-11 — Settings source of truth migration to v2
We standardized on `server/db/pricebot.settings.json` keyed by merchantId. UI writes via `/api/pricebot/settings` with `storeId` as merchantId; routes (opponents/run/export) now read v2 fields (minPrice/maxPrice/stepKzt/ignoredOpponents). Legacy `pricebot.json` helpers remain for backward compatibility but are not used for new writes.

## 2025-08-11 — Dry-run by default for repricing
All run/bulk actions default to dry-run and require explicit confirmation to apply, to prevent accidental price changes.

## 2025-08-11 — Import validation with zod + preview
Imports are validated first; errors are typed and shown as toasts. No mutation occurs until the user confirms a clean import.

## 2025-08-11 — Conventional commits and small diffs
We keep commits small and descriptive (Conventional Commits) to simplify reviews and bisects in production.
