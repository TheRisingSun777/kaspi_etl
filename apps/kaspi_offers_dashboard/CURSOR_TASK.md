You are a senior full‑stack engineer. Repo root: kaspi_etl. App: apps/kaspi_offers_dashboard (Next.js App Router + TypeScript + Tailwind + Playwright).
Goal: finalize the Offers dashboard, then add a Pricebot section that manages our store’s active offers and auto‑reprices within min/max guardrails.
Do not stop until all acceptance criteria at the bottom are green.

0) Status audit (from current build)
	•	✅ Dashboard renders with search by masterProductId + city; variants grid with sellers & Δ vs min; analytics (avg/median/max spread, bot share, attractiveness), CSV/XLSX export, “Include out‑of‑stock” toggle, and Copy JSON.  
	•	⚠️ “Fastest Delivery” KPI shows “—” ⇒ delivery parsing not computed/propagated.  
	•	⚠️ PriceBot labels appear, but the detection looks heuristic-only; keep but mark as heuristic.  
	•	⛔ Unknown/likely missing: LRU cache for analyze responses; debug artifact dump; unit tests; secret hygiene enforced; scraper resiliency (sellers tab + city cookie) re‑verified.

Implement/verify everything below.
{ "scripts": { "dev":"next dev","build":"next build","start":"next start","typecheck":"tsc --noEmit","lint":"eslint .","test":"vitest run","test:watch":"vitest" } }	
3.	Next config: allow images from *.kaspi.kz. Keep reactStrictMode: true.

⸻

2) Types & analytics (tighten)
	•	Ensure a single source of truth types file: lib/types.ts containing Seller, Variant, AnalyzeResult and analytics fields (avg/median/max spread, botShare, attractivenessIndex 0–100, stabilityScore 0–100, bestEntryPrice).
	•	Keep lib/analytics.ts with: basicStats, computeVariantStats, computeGlobalAnalytics (already works as per UI numbers), and add fastestDelivery aggregator (min by normalized ETA string). Wire it into the KPI card (no more “—”).  

⸻

3) Scraper resiliency & caching
	•	In server/scrape.ts:
	•	Always set city cookie and use ?c=${cityId}.
	•	Programmatically open sellers tab (Продавцы / Все предложения) and capture JSON responses; fall back to DOM parse for seller rows.
	•	Normalize delivery text and include it on each seller; return a product‑level fastestDelivery (min ETA).
	•	Sequential variant scraping (Kaspi rate‑limits); cap to 20 variants.
	•	Add a tiny in‑memory LRU (server/cache.ts) with 5‑minute TTL keyed by {masterProductId}:{cityId} to avoid re‑scrapes when toggling UI.
	•	Add DEBUG_SCRAPE=1 to dump HTML/JSON artifacts for one variant for regression tests.

⸻

4) API contracts
	•	POST /api/analyze → input { masterProductId, cityId? } → returns AnalyzeResult with analytics + fastestDelivery.
	•	Error policy: 400 on validation, 429 on rate‑limit, 503 on timeouts; always return { variants: [] } so UI doesn’t crash.

⸻

5) Export helpers
	•	lib/export.ts: fix CSV/XLSX to flatten (variant × sellers) rows with meta (variantId, size/color, rating, min/median/max/spread/stddev, seller, price, delivery). Ensure export respects the Include out‑of‑stock toggle.

⸻

6) UI polish (first section)
	•	KpiCards: render fastestDelivery, uniqueSellers, attractiveness.
	•	SearchBar: correct Shymkent ID 620000000; keep recent‑search chips.
	•	VariantCard/SellersTable: Δ vs min by variant, green highlight for min; show “PriceBot?” badge using simple regex heuristic (/bot|бот/i).
	•	Ensure Include OOS affects both grid and export.

⸻

7) Pricebot Dashboard (new second section)

7.1 Server: Merchant API client

Create server/merchant/client.ts:
	•	Config:
	•	KASPI_MERCHANT_API_BASE (env; default to provided base when known).
	•	KASPI_MERCHANT_ID = 30141222.
	•	KASPI_MERCHANT_API_KEY (server‑only).
	•	Implement helpers with proper headers (add both; the correct one will be used by the API you configure):
	•	Authorization: Bearer <key> and X-Auth-Token: <key> (pick whichever works; expose via config).
	•	Accept: application/json, User-Agent: KaspiOffersDashboard/1.0.
	•	Endpoints (names are stable; the exact paths may differ per Kaspi deployment—auto‑discover if needed via the merchant panel or existing scripts):
	•	listActiveOffers(merchantId) → returns our current offers list with variantProductId, name, price, stock, category.
	•	updatePrice(offerId|variantProductId, newPrice) → updates price for a single variant.
	•	updatePricesBulk([{ variantProductId, price }]) → bulk update with small batches (size 10–20) and backoff on 429.
	•	Resilience: 429/503 backoff with jitter (start 1s → 8s, max 3 retries). Full error surface returned to caller.

If the exact REST shape differs, inspect the merchant panel network calls and adapt client methods accordingly. Keep the method signatures above unchanged so the UI and bot logic don’t care about transport details.

7.2 Data store: pricing rules + ignores

Create SQLite (simple, local) via better-sqlite3 at server/db/pricing.sqlite. Add DAO server/db/rules.ts with tables:
	•	pricing_rules(variant_id TEXT PRIMARY KEY, min_price INTEGER NOT NULL, max_price INTEGER NOT NULL, step INTEGER NOT NULL DEFAULT 1, interval_min INTEGER NOT NULL DEFAULT 5, active INTEGER NOT NULL DEFAULT 1, updated_at DATETIME)
	•	ignored_sellers(variant_id TEXT, seller_name TEXT, PRIMARY KEY (variant_id, seller_name))

Migrations: create tables if not exist on boot. All prices in KZT (integers).

7.3 API for Pricebot

Create routes:
	•	GET /api/pricebot/offers → combine merchant offers with current rules; returns { name, variantProductId, ourPrice, rules: {min,max,step,interval,active}, opponentCount, opponents?: Seller[] }.
	•	PUT /api/pricebot/rules/:variantId → upsert { minPrice, maxPrice, step, intervalMin, active }.
	•	PUT /api/pricebot/ignore/:variantId → { sellerName, ignore: boolean }.
	•	POST /api/pricebot/reprice/:variantId → runs reprice once for one variant (returns oldPrice, targetPrice, reason).
	•	POST /api/pricebot/reprice-bulk → runs on all active=1 rules (rate‑limited, batched).

For opponents, reuse the same sellers data we already know how to scrape: call our /api/analyze for the variant’s product page (same city). This keeps one source of truth for competitor prices.

7.4 UI: “Pricebot” section (second section on the page)

Under the existing analytics, render a new card “Pricebot (Store 30141222)” with a table:
	•	Columns: Name, Variant ID, Our Price, Min Price (input), Max Price (input), Step (input), Interval min (1–10), Opponents (N) (clickable link opening modal), Active (toggle), Reprice (Run), Save.
	•	“Opponents (N)” opens a modal with a sorted asc list: {sellerName, price} and a small ignore toggle next to each seller. Clicking saves via /api/pricebot/ignore/:variantId.
	•	“Run” triggers one‑off reprice for that variant.
	•	At top of the section: Run All (bulk), Dry‑run mode toggle (no price push), and Logs drawer that streams last 100 actions.

7.5 Pricebot algorithm (deterministic, safe)

Given {minPrice, maxPrice, step, intervalMin, active}, and competitor list C for the same variantId and city:
	1.	Filter out ignored_sellers and our own store names (self).
	2.	Compute competitorMin = min(price in C); if none: target = maxPrice (ceiling).
	3.	If competitorMin < ourPrice: target = max(minPrice, competitorMin - step).
	4.	Else: **target = clamp(competitorMin, minPrice, maxPrice)** (do not raise above maxPrice`).
	5.	Round to nearest 1 KZT (integer).
	6.	Only push update if abs(target - ourPrice) >= step and target changed since last run.
	7.	Backoff on 429; skip a variant after 3 consecutive failures for 15 minutes (circuit breaker).

Note: Treat bot‑heavy markets carefully: if the number of distinct sellers within ±10 KZT of competitorMin ≥ 3, do not undercut—match competitorMin but never go < minPrice. (This caps bot wars.)

7.6 Scheduler
	•	Use node-cron inside a server‑only module server/pricebot/scheduler.ts.
	•	Every minute, pick variants with active=1, then run those whose intervalMin divides the current minute index (or use per‑variant next‑run timestamps).
	•	Ensure only one job at a time (mutex). Batch updates (10–20 per batch) with short sleeps.

⸻

8) Tests
	•	Unit:
	•	lib/analytics.test.ts → stats + attractiveness + stability + fastestDelivery aggregator.
	•	server/pricebot/logic.test.ts → given (rules, ourPrice, competitors) assert targetPrice. Include cases: undercut, ceiling, min guard, bot‑dense “match not undercut”.
	•	Integration (mocked):
	•	Merchant client mocked (no live calls).
	•	Scrape parser tests with stored HTML fixtures (dumped by DEBUG_SCRAPE=1).

⸻

9) Observability
	•	Add a minimal logger (server/log.ts) with levels; write recent pricebot actions to a ring buffer exposed at /api/pricebot/logs.
	•	UI “Logs” drawer polls this endpoint every ~5s when open.

⸻

10) Documentation
	•	Update README.md with envs:
	•	KASPI_MERCHANT_API_KEY (server‑only; never NEXT_PUBLIC_), KASPI_MERCHANT_ID=30141222, KASPI_MERCHANT_API_BASE, DEFAULT_CITY_ID, NEXT_PUBLIC_DEFAULT_CITY_ID.
	•	Add a Security note: do not commit .env.local; rotate keys if leaked; mask secrets in logs.

⸻

Acceptance criteria (don’t stop until all pass)
	1.	pnpm typecheck && pnpm build && pnpm test all green.
	2.	Dashboard KPIs show Fastest Delivery (not “—”), unique sellers count, attractiveness; numbers sensible.  
	3.	Export CSV/XLSX contain (variant × sellers) rows and respect the OOS toggle.
	4.	LRU cache reduces repeat analyze latency within 5 minutes.
	5.	Pricebot section shows our active offers with editable min/max/step/interval, an Opponents (N) link → modal with sorted list + per‑seller ignore toggles, Active switch, Run (single) and Run All (bulk).
	6.	Price updates honor guards (never below min, never above max), respect step size, and throttle/backoff on 429.
	7.	Scheduler drives periodic repricing; dry‑run mode produces logs without pushing prices.
	8.	README updated; no secrets in git history.

⸻

Troubleshooting notes (future‑proof)
	•	Merchant API shapes differ by cluster; if Authorization doesn’t work, try X-Auth-Token or X-Auth-ApiKey. Inspect the merchant portal network calls and adapt client.ts without changing UI/logic signatures.
	•	If competitor scraping returns 0 sellers, reload once with city cookie + ?c= set; then skip with a helpful error.
	•	Keep selectors tolerant; prefer captured JSON over DOM when available.
	•	If bot wars detected (≥3 sellers within ±3 KZT of the min), match not undercut.
	•	Always round prices to integer KZT and batch updates.

⸻

Done = ship report

When everything is done, output:
	1.	A brief engineering report of what changed and how validated.
	2.	Commands to run the dashboard + pricebot locally.
	3.	Known limitations + next bets.

Stop only when all acceptance criteria above are met.