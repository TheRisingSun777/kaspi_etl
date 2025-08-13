# OPERATING.md — Agent Operating Rules (Repo Memory)

**Purpose**  
Keep working memory in the repo so work can resume even if the chat resets.

## Single Source of Truth
- `TASKS.yaml` — backlog, in‑progress, done; each with acceptance criteria (AC).
- `PROGRESS.md` — compact, timestamped logs (1–3 bullets per change).
- `STATE.json` — lightweight runtime state (branch, merchant/store/city, last runs, flags).
- `DECISIONS.md` — non‑obvious choices with 3–5 lines of rationale.

## Work Loop
1. Read `STATE.json` and `TASKS.yaml`.
2. Pick the top item from `in_progress`; if empty, take top of `backlog`.
3. Implement in small commits on `STATE.branch` (default `feat/offers-dashboard`).
4. Test locally; default all price updates to **dry‑run**.
5. Update `PROGRESS.md`, `STATE.json`, and `TASKS.yaml` (move the task / tick ACs).
6. Only ask questions when blocked; otherwise continue.

## Commit & Branching
- Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.
- One logical change per commit; reference the task id (e.g., `feat(run-001): bulk run API`).
- Keep diffs small where practical (<200 LOC).

## Safety
- Never commit secrets or cookies. Use local files (e.g., `server/cookies/{merchantId}.json`) and keep them in `.gitignore`.
- Repricing endpoints run **dry by default**; require explicit confirmation to apply.
- Validate all import/user inputs with zod; surface typed errors to the UI with toasts.
 - Cookie refresh: run `node apps/kaspi_offers_dashboard/server/scripts/login.mjs <merchantId>` and then verify via `POST /api/auth/cookie-status`.
 - Cookie refresh (alt): quick grab from running Chrome profile via CDP:
   1) Start Chrome with your UNI profile and remote debugging:
      `open -na "Google Chrome" --args --profile-directory="UNI" --remote-debugging-port=9222 https://kaspi.kz/shop/p/-131138247/?c=710000000`
   2) Ensure you are logged in and the product page loads sellers.
   3) In the app dir, run: `pnpm cookies:collect` (defaults to merchant 30141222, city 710000000)
   4) The cookie is saved to `apps/kaspi_offers_dashboard/server/merchant/<merchantId>.cookie.json`.
When the chat approaches 80 % of the token limit, checkpoint your work to PROGRESS.md, update STATE.json, and start a new chat with the unified intro prompt. This prevents context loss.

## Interfaces (current expectations)
(All accept `merchantId`; where applicable also `storeId` and `cityId`.)
- `GET /api/merchant/offers?q=` — live offers; normalized stock fields.
- `GET /api/pricebot/opponents?productId=&cityId=&merchantId=` — sellers; cache ≈3 minutes; includes `isYou` and `isIgnored`.
- `GET|POST /api/pricebot/settings` — persists in `server/db/pricebot.settings.json` (v2).
- `GET /api/pricebot/export?format=csv|xlsx`
- `POST /api/pricebot/import` — validate with zod; preview mode supported.
- `POST /api/pricebot/run` — single SKU (dry by default).
- `POST /api/pricebot/bulk` — chunked multi‑SKU runs (dry by default).
- `GET /api/pricebot/stats` — KPIs for dashboard tiles.
 
### Watchers
 - Price Watch (`scripts/price_watch.ts`): calls `/api/pricebot/run?dry=true` for due SKUs by `intervalMin`.
   - Usage: `pnpm tsx apps/kaspi_offers_dashboard/scripts/price_watch.ts --merchantId=30141222 --city=710000000 --pollSec=60`
   - Env: `PRICEBOT_API_BASE` (default `http://localhost:3001`), `PRICE_WATCH_POLL_SEC`.
   - Logs proposals like: `[run][30141222] SKU123: our=1099 → target=1050 (undercut)`

## UI Notes
- `PricebotTable` scopes calls by selected `storeId`.
- `OpponentsModal` uses `merchantId`; honors global + per‑SKU ignore lists.
- Zero‑stock rows are greyed out and auto‑inactive.

## Quality Bar
- Light tests where practical; handle transient upstream failures with retries + caching.
- Keep `PROGRESS.md` tiny—no huge JSON dumps.
- Add a `DECISIONS.md` entry whenever you make a non‑obvious trade‑off.

