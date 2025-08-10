
# Cursor Master Prompt — Kaspi Offers Dashboard (Unified, Step‑by‑Step)

**Repo:** https://github.com/TheRisingSun777/kaspi_etl  
**Branch:** `feat/offers-dashboard`  
**App path:** `apps/kaspi_offers_dashboard`  

You are a **senior full‑stack engineer** tasked with turning this dashboard into a reliable, production‑ready tool. **Do all tasks in this file, in order.** Work **only** inside `apps/kaspi_offers_dashboard` and minimal root configs (`tsconfig`, workspace, eslint) when required.

---

## 0) Setup & ground rules

- Node ≥ 18, pnpm ≥ 8. Use the repo’s lockfile.  
- **Never** spawn more than **2 Playwright pages at once**. Avoid opening lots of tabs. Close pages you open.  
- Keep code TypeScript‑strict, small, and well‑typed.  
- Prefer **Playwright** server‑side scraping from API route for deterministic runs.  
- Create reusable **selectors/utilities**; avoid hardcoding fragile CSS classnames where possible.  
- Add **feature flags via env** (document them in README):
  - `PW_HEADLESS=0|1` (default 1)
  - `PW_SLOWMO=0|250`
  - `DEBUG_SCRAPE=0|1`
  - `SCRAPE_MAX_TABS=1|2` (default 1)
  - `SCRAPE_CONCURRENCY=1|2` (default 1)
  - `SCRAPE_TTL_SEC=180` (cache per `productId+cityId`)

If a step requires edits outside the app folder, keep them minimal and explain in the PR description.

Deliverable for every major step: **commit with a clear message** and a short summary in the terminal log.

---

## 1) Fix the scraper (`server/scrape.ts`)

### 1.1 Root causes to eliminate
- Log `captured=0 parsedFromCaptured=0` and 0 sellers: we never capture the XHR JSON, city modal blocks network, and we block styles/JS.  
- Variants lack **color/size**; rating missing; delivery dates absent.  
- Multiple Chrome tabs opening → no concurrency guard and we don’t close variant pages.

### 1.2 Required behavior
For each **masterProductId** and **cityId**:
1. **Open with correct city**  
   - Always navigate with `?c=<cityId>`; also set cookie `kaspi_city_id=<cityId>` for domain `.kaspi.kz`.  
   - If the **“Выберите ваш город”** modal appears, click the matching city link:  
     - Astana/Nur‑Sultan → `710000000`  
     - Almaty → `750000000`  
     - Shymkent → `620000000`  
   - Wait for the modal to disappear; take a `DEBUG_SCRAPE` screenshot on failure.
2. **Network policies**  
   - Intercept routes; **block** `image`, `media`, `font`. **Allow** stylesheets and JS.  
   - Set UA to a recent Chromium; set `locale: 'ru-KZ'`.
3. **Navigate the page**  
   - On each variant page, **click the sellers tab** by text: `/продавц/i` OR “Все продавцы/предложения”.  
   - Scroll several times; wait for network idle (or 500–900ms between scrolls) to trigger XHRs.
4. **Capture JSON**  
   - Listen to `response` events; if `content-type` includes JSON and URL matches  
     `offer|seller|merchant|price|catalog|stock|availability|aggregate|buybox` → collect JSON.  
   - Parse sellers: `name`, `price`, `deliveryDate` (look for nested objects; normalize).  
5. **DOM fallback** when no JSON: parse rows with a “Выбрать” button and nearby price/delivery nodes.  
6. **Extract variant meta**  
   - `variantColor`: from the “Цвет” property row, or selected color option, or heuristics from H1 (e.g., “черный/белый/серебристый”).  
   - `variantSize`: from size dropdown/selected value or title snippet (e.g., “48/L RUS”).  
   - `rating`: from JSON‑LD (`aggregateRating`), or visible rating block (`avg`, `count`).
7. **Retries**: if no sellers after first pass, retry click+scroll+parse **up to 2 times**.  
8. **Stats per variant**: compute `min`, `median`, `max`, `spread = max−min`, `stddev`, `sellersCount`.  
9. **Price‑bot suspects**: `isPriceBot = price <= minPrice + 1` (KZT) or if it undercuts previous min by 1‑50 KZT across ticks (hook exposed for watch script).  
10. **Concurrency & cleanup**: open **one variant page at a time** (configurable), ensure pages are **closed**. Avoid tab explosions.
11. **Cache**: in‑memory LRU by `(masterProductId, cityId)` with TTL `SCRAPE_TTL_SEC` to speed repeated calls during dev.

### 1.3 Return types
```ts
export type Seller = {
  name: string;
  price: number;
  deliveryDate?: string;
  isPriceBot?: boolean;
};

export type Variant = {
  productId: string;
  label: string;          // h1 or size/variant text
  variantColor?: string;
  variantSize?: string;
  rating?: { avg?: number; count?: number };
  sellersCount: number;
  sellers: Seller[];
  stats: { min?: number; median?: number; max?: number; spread?: number; stddev?: number };
};

export type AnalyzeResult = {
  masterProductId: string;
  productName: string;
  cityId: string;
  variants: Variant[];
  uniqueSellers: number;
  analytics: {
    avgSpread?: number; medianSpread?: number; maxSpread?: number;
    botShare?: number; attractivenessIndex?: number; // 0..100
  };
  meta: { scrapedAt: string; source: 'kaspi.kz'; notes?: string; debug?: any };
};
```

### 1.4 Logging (behind `DEBUG_SCRAPE=1`)
- Log counters: `capturedJSON`, `parsedFromJSON`, `parsedFromDOM`.  
- Save 1 screenshot for “city modal not closed” and 1 for “no sellers” per variant (to a `data_raw/debug/` folder).

---

## 2) Enhance the API route (`app/api/analyze/route.ts`)

- Call `scrapeAnalyze(masterProductId, cityId)` with the improved logic.  
- Aggregate master‑level metrics:
  - `uniqueSellers` (dedupe by normalized name).  
  - `avgSpread`, `medianSpread`, `maxSpread`.  
  - `botShare` = flagged sellers / total sellers.  
  - `attractivenessIndex` in `0…100` (explicit formula combining spread ratio, competition, bot share, average rating; keep weights readable).  
- Ensure response **always** includes `variantColor`, `rating`, `deliveryDate`, `stats`, `isPriceBot` when available.

---

## 3) Price watch script (`scripts/price_watch.ts`)

- CLI: `--ids=108382478,121207970 --city=710000000 --intervalSec=300`.  
- Every tick: call the scraper for each id, append **NDJSON** to `data_raw/watch/<id>.ndjson`:
  ```json
  {"ts":"2025-08-09T12:34:56Z","variantId":"121207970","variantColor":"черный","seller":"ShopKZ","price":2810,"deliveryDate":"Вт, 12 августа","isPriceBot":false}
  ```
- Maintain in‑memory sliding window per `(variantId, seller)` to observe undercuts; flag price‑bots that repeatedly set `price <= min + 1`.  
- Log concise summaries each tick (min/median/max/spread/sellers/bot suspects).  
- `package.json` script:
  ```json
  "watch:prices": "tsx scripts/price_watch.ts --ids=108382478,121207970 --city=710000000 --intervalSec=300"
  ```

---

## 4) UI & design overhaul (Apple‑inspired)

- Use **Inter variable** via `next/font/google`; set as default with **SF Pro** fallbacks.  
- Update `tailwind.config.ts` tokens:
  - background `#0A0A0C`, card `#121214`, textPrimary `#F5F5F7`, textSecondary `#A1A1AA`,
  - primary `#0A84FF`, accentMuted `#64D2FF`, borders `rgba(255,255,255,.06)`.
- Components:
  - **KpiCards**: Product Name, Total Variants, **Total Unique Sellers**, Fastest Delivery, **Attractiveness Index**.  
  - **VariantCard**: color chip, rating (`★ avg · count`), stats (min/median/max/spread/σ), seller count.  
  - **SellersTable**: columns → Seller, Price, Δ vs Min, **PriceBot?**, DeliveryDate. Highlight lowest price.  
  - **Analytics** section at top: avg/median/max spread, botShare, attractiveness index (with tooltips).  
- Keep export actions (CSV/XLSX/JSON). Provide loading skeletons and great empty/error states.  
- Remove Vite remnants if any (`vite`, `@vitejs/plugin-react`).

---

## 5) City‑aware delivery

- Delivery text **must reflect selected city**. Validate with `710000000` (Astana), `750000000` (Almaty), `620000000` (Shymkent).  
- Add a small city switcher state in the UI; cache last selection in localStorage.  
- Surface a “Fastest delivery” KPI based on parsed dates.

---

## 6) Performance & reliability

- LRU cache (TTL env) at scraper layer.  
- Backoff on HTTP/anti‑bot signals; randomize delays (100–400ms).  
- Clean close of pages/contexts/browsers.  
- Concurrency guard so we never open > 2 tabs.  
- Optional proxy hooks (env placeholders) documented in README.

---

## 7) Documentation & tests

- Update `README.md` inside the app:
  - Setup, env vars, running dev/prod.  
  - How the scraper works, metrics, heuristics, and limitations.  
  - How to run `watch:prices`.  
- Test IDs: `108382478`, `121207970` for cities Astana/Almaty/Shymkent; ensure sellers + delivery + color/size + ratings appear consistently.

---

## 8) Quick wins (deliver in hours)

- Fix city modal handling; ensure sellers appear for 121207970 in Astana.  
- Add Δ vs Min + PriceBot flag in table.  
- Add color/size parsing + rating.  
- Compute spreads & attractiveness index.  
- Polish typography (Inter), palette, borders.  
- Close pages; cap concurrency; no more tab explosions.

---

## 9) Code quality & commit

- Small, reviewable commits:
  - `feat(scrape): city handling + JSON capture + DOM fallback`
  - `feat(metrics): price stats + bot flags`
  - `feat(ui): Inter, tokens, KPI & tables`
  - `feat(api): analytics + attractiveness index`
  - `chore: docs + scripts/watch`
- Final PR comment: summarize what works, what’s flaky, and next steps.

---

## 10) Final validation checklist

- [ ] City modal auto‑selects correct city and disappears.  
- [ ] Sellers captured (JSON or DOM) with delivery dates.  
- [ ] Variant color/size populated; per‑variant rating present when available.  
- [ ] Stats (min/median/max/spread/stddev) computed; Δ vs min visible.  
- [ ] Price‑bot suspects flagged.  
- [ ] Unique sellers & attractiveness index computed.  
- [ ] UI uses Inter + Apple‑style palette; skeletons look good.  
- [ ] Tabs/pages are closed; no explosion; run fits in < 60s for 121207970.  
- [ ] README updated; watch script runs.  

**Go implement now.**
