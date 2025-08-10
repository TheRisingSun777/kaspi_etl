# Kaspi Offers Insight — MASTER TASK (v2025‑08‑10)

**Single source of truth for Cursor.**  
Work in `apps/kaspi_offers_dashboard` only. TypeScript strict. No secrets in git. Small, reviewable commits.

## Agent Ops (non‑blocking)
- Do **not** pause between steps. Auto‑apply patches and run shell/git.
- If port `3000` is taken, automatically use `PORT=3001`.
- If a command fails, retry once; otherwise log the error to `apps/kaspi_offers_dashboard/CURSOR_PROGRESS.md` and continue with the rest.
- **Never edit** `.gitignore`, `.env*`, lockfiles automatically. If a change is needed, print the exact diff to `CURSOR_PROGRESS.md`.
- Stop **only** when all acceptance checks at the bottom are green.

## Pre‑flight
- Ensure `.env.local` exists locally with a valid cookie or API key.  
- If `GET /api/debug/merchant` returns `401`, do not block other work; log “REFRESH COOKIE” and continue, but keep the loader tolerant.

---

## PHASE A — Merchant client + debug routes (harden headers)
**Goal:** centralize MC headers and auth (cookie or API key), add debug list endpoint.

1) Create/adjust `lib/kaspi/client.ts`:
   - `mcFetch(path, init)` adds headers:
     - `Origin: https://kaspi.kz`
     - `Referer: https://kaspi.kz/`
     - `x-auth-version: 3`
     - `Accept: application/json, text/plain, */*`
     - `Accept-Language: ru-RU,ru;q=0.9`
     - realistic `User-Agent`
     - auth: cookie via `KASPI_MERCHANT_COOKIE` (cookie mode) or `Authorization: Bearer ${KASPI_MERCHANT_API_KEY}` (token mode).
   - `getMerchantId()` throws if missing.

2) Debug endpoints:
   - `app/api/debug/merchant/route.ts` → GET count endpoint:  
     `/offers/api/v1/offer/count?m=${MID}` → `{ ok:true, data }` or `{ ok:false, status }`
   - `app/api/debug/merchant/list/route.ts` → raw list dump for two param sets:
     - `paramset=a`: `/bff/offer-view/list?m=${MID}&p=0&l=50&a=true&t=&c=&lowStock=false&notSpecifiedStock=false`
     - `paramset=available`: `/bff/offer-view/list?m=${MID}&p=0&l=10&available=true&t=&c=&lowStock=false&notSpecifiedStock=false`
     - If `?raw=1`, return raw JSON. Else return `{ pickedKey, length }` using the same array‑key picker as the offers route (below).

---

## PHASE B — Offers loader (bulletproof)
**Goal:** make `/api/merchant/offers` return items on any reasonable cluster shape.

3) Update/create `app/api/merchant/offers/route.ts`:
   - Call the `a=true` variant first (p=0,l=50).
   - If no array is found or it’s empty, try the `available=true` variant (p=0,l=10).
   - Implement `pickArrayKey(obj)` to search (in order):  
     `items, content, data.items, data.content, list, offers, results, rows, page.content`
   - Normalize each row defensively:
     ```ts
     const sku = it.merchantSku || it.sku || it.offerSku || it.s || it.id || '';
     const productId = Number(it.variantProductId ?? it.productId ?? it.variantId ?? 0);
     const name = it.name || it.title || it.productName || '';
     const price = Number(it.price ?? it.currentPrice ?? it.offerPrice ?? it.value ?? 0);
     const stock = Number(it.stock ?? it.available ?? it.qty ?? 0);
     ```
   - If still empty, return `{ ok:true, items: [], debug: { tried: 2, pickedKey, hints: ['/api/debug/merchant/list?raw=1'] } }`.

---

## PHASE C — Pricebot storage + settings (simple JSON)
4) Create `lib/pricebot/storage.ts` (if absent) with:
   - `readStore()`, `writeStore()`, `getSettings(sku)`, `upsertSettings(sku, patch)`, `toggleIgnore(sku, seller, ignore)`.
   - Path: `apps/kaspi_offers_dashboard/server/db/pricebot.json` (gitignored).

5) Endpoints:
   - `GET /api/pricebot/offers` → merge MC rows + settings.
   - `PATCH /api/pricebot/settings/[sku]` → upsert settings.
   - `POST /api/pricebot/ignore-seller` → toggle seller ignore.

---

## PHASE D — Reprice (already works; keep stable)
6) Ensure `app/api/pricebot/reprice/route.ts`:
   - Body: `{ sku, price, cityId }`
   - POST MC `/price/trends/api/v1/mc/discount` with:
     ```json
     { "merchantUID": "<MID>", "merchantSKU": "<sku>", "entries": [{ "city": "<cityId>", "price": <price> }] }
     ```
   - Return raw array or wrap single object in array. Surface `rejectReason` and `firstSuitableDate` unchanged.

---

## PHASE E — Pricebot UI (table + opponents modal)
7) `components/pricebot/PricebotTable.tsx` (or existing panel):
   - On mount, GET `/api/pricebot/offers`.
   - If `items.length===0`, render a banner:  
     “No offers returned. Debug: see /api/debug/merchant/list?raw=1” and show any `.debug` payload.
   - Table columns: **Name**, **SKU**, **Variant**, **Our Price**, **Stock**, **Min**, **Max**, **Step**, **Interval(1–10)**, **Active**, **Opponents (N)**, **Run**.
   - Opponents link → modal: GET `/api/merchant/offer/[sku]`, list sellers ASC by price, with **ignore** button writing to `/api/pricebot/ignore-seller`.
   - “Run” posts to `/api/pricebot/reprice` with `{ sku, price, cityId: process.env.NEXT_PUBLIC_DEFAULT_CITY_ID || '710000000' }`.

---

## PHASE F — Docs / Troubleshooting
8) Update app `README.md`:
   - How to set `.env.local` (cookie vs API key).
   - What the debug endpoints do.
   - Why “NOT_ENOUGH_HISTORY” appears and how to read `firstSuitableDate`.

---

## Acceptance checks (don’t stop until all are green)
- [ ] `GET /api/debug/merchant` → `{ ok:true }` (if 401, log and continue building).
- [ ] `GET /api/merchant/offers?p=0&l=50` → returns **items > 0** on first or fallback call; otherwise returns `items:[]` with a `debug` object and **raw** endpoint works.
- [ ] Pricebot page **does not** silently show a blank table: either items render, or the banner with debug hint is visible.
- [ ] `POST /api/pricebot/reprice` still returns the real MC response (incl. `NOT_ENOUGH_HISTORY` and `firstSuitableDate`).
- [ ] Settings persist to `server/db/pricebot.json` and “ignore seller” works.
- [ ] No secrets committed. Types pass. Build passes.