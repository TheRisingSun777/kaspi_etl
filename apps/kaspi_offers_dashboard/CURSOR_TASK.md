Repo: https://github.com/TheRisingSun777/kaspi_etl
Branch: feat/offers-dashboard
App path: apps/kaspi_offers_dashboard

You are a senior full-stack engineer. Follow this task list to make the Kaspi Offers dashboard production-ready. Work ONLY in the `apps/kaspi_offers_dashboard` directory and any required minimal config files. Commit after each numbered section. Stop only when all tasks are finished.

──────────────────────────────────────────────────────────────────────────────
## 1. Fix scraping reliability and city selection

- Inspect `server/scrape.ts` and fix why logs show `captured=0 parsedFromCaptured=0`. Sellers remain empty because the city overlay isn’t dismissed and the sellers tab isn’t clicked.
- **City control**: Always append `?c=<cityId>` to product URLs AND set the `kaspi_city_id` cookie. Detect and click the correct city in the “Выберите ваш город” modal (support 710000000=Astana/Nur‑Sultan, 750000000=Almaty, 620000000=Shymkent). If the modal persists, reload the URL with the query and cookie set.
- **Resource blocking**: Block only images/media/fonts; allow CSS and JS so the DOM and scripts load correctly.
- **Concurrency**: Use a single Playwright browser context and limit to ≤2 pages at once (use a queue or p-limit). Close each page after scraping to avoid many open tabs.
- **Variant scraping** for each variantId:
  1. Go to `https://kaspi.kz/shop/p/-<id>/?c=<cityId>` with the cookie set.
  2. Click the sellers tab (texts like “Продавцы”, “Все продавцы”, “Все предложения”) if present.
  3. Scroll down several times and wait for `networkidle`; this triggers XHR calls.
  4. Capture JSON from responses whose URL contains `offer|seller|merchant|price|catalog|stock|availability|reviews|rating`. Parse sellers: `name`, `price`, `deliveryDate`. If JSON capture is empty, fall back to DOM rows with a “Выбрать” button; parse seller name, price (digits only), and delivery text.
  5. Extract `variantColor` from “Цвет” row or selected colour chip; fallback to keywords in H1 (черный, белый, синий, красный, серый, зелёный, фиолетовый, бежевый).
  6. Extract `variantSize` from “Размер” row or selected size button; fallback to tokens in H1.
  7. Parse per‑variant **rating** from JSON‑LD (`aggregateRating.ratingValue` and `reviewCount`), or meta tags (`itemprop="ratingValue"`/“ratingCount”), or visible rating text next to stars. Save as `{ avg: number, count: number }`.
  8. Retry the click‑scroll‑parse cycle up to 2 times if no sellers were found.
- **Stats and flags**: Compute per‑variant `min`, `median`, `max`, `spread=max-min`, `stddev`, `sellerCount`. Flag `isPriceBot` if a seller price ≤ `(minPrice + 1 KZT)`.
- **Return structure**:
  ```ts
  type Seller = { name: string; price: number; deliveryDate?: string; isPriceBot?: boolean };
  type Variant = {
    productId: string;
    label: string;           // page title or size text
    variantColor?: string;
    variantSize?: string;
    rating?: { avg?: number; count?: number };
    sellersCount: number;
    sellers: Seller[];
    stats?: { min?: number; median?: number; max?: number; spread?: number; stddev?: number };
  };
* Debug mode: If DEBUG_SCRAPE=1, log captured counts (capturedJSON, parsedFromJSON, parsedFromDOM), save page HTML to data_raw/debug/variant_<id>.html, and screenshots for unresolved city modal or empty sellers.
──────────────────────────────────────────────────────────────────────────────
2. Enhance API route (app/api/analyze/route.ts)
* Import and call the new scrapeAnalyze(masterProductId, cityId) with the ?c=<cityId> query.
* Compute master‑level metrics:
    * uniqueSellers: count of distinct seller names across all variants.
    * avgSpread, medianSpread, maxSpread: calculated only across variants with ≥2 sellers.
    * botShare: ratio of sellers flagged as isPriceBot.
    * attractivenessIndex: a weighted formula (0–100) that balances margin opportunity and competition/demand. Use weights like:spreadRatio = median(spread / medianPrice) (clipped 0–1),competitionPenalty = 1 − min(1, sellerCount/12),ratingBoost = normalized(avgRating, 3.5→4.8),botPenalty = 1 − botShare.Combine them into a 0–100 score (e.g., 40% spreadRatio + 30% competitionPenalty + 20% ratingBoost + 10% botPenalty).
* Return JSON with:
    * masterProductId, productName, cityId,
    * variants: Variant[],
    * uniqueSellers,
    * analytics: { avgSpread, medianSpread, maxSpread, botShare, attractivenessIndex },
    * meta: { scrapedAt: ISO string, source: 'kaspi.kz', notes?: string }.
──────────────────────────────────────────────────────────────────────────────
3. Implement price watch script
* Create scripts/price_watch.ts (ts-node via tsx).
* Accept CLI args: --ids (comma‑separated master IDs), --city (default 710000000), --intervalSec (default 300).
* At each interval:
    1. Run the scraper for each master ID.
    2. Append NDJSON entries to data_raw/watch/<masterId>.ndjson:{ ts: "...ISO...", variantId, variantColor, variantSize, seller, price, deliveryDate, isPriceBot }.
    3. Maintain an in‑memory sliding window per (variantId, seller) to update isPriceBot if the seller repeatedly undercuts the min price by ≤50 KZT over the last few ticks.
    4. Log a summary: minPrice, maxPrice, spread, sellerCount, suspectedBots (names).
* Add "watch:prices": "tsx scripts/price_watch.ts --ids=108382478,121207970 --city=710000000 --intervalSec=300" to package.json.
──────────────────────────────────────────────────────────────────────────────
4. Apple-inspired UI & analytics
* Use Inter via next/font/google with fallback -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif.
* Update tailwind config with an Apple‑style dark palette:
    * bg: #0A0A0C, card: #121214, textPrimary: #F5F5F7, textSecondary: #A1A1AA, accent: #0A84FF, accentMuted: #64D2FF, border: rgba(255,255,255,0.06), soft shadows.
* Components:
    * SearchBar: master product ID input, city selector limited to {Astana/Nur‑Sultan, Almaty, Shymkent}, and memory of last two IDs.
    * ModelCard: product image (if accessible), product name, chips for available colours (dedup variantColor), chips for available sizes (from variant IDs), and overall rating.
    * KpiCards: show Product Name, Total Variants, Total UNIQUE Sellers, Fastest Delivery (in days), Attractiveness Index (colour-coded).
    * VariantCard: show variantColor swatch, variantSize, rating, sellersCount, stats (min, median, max, spread, σ), and a table of sellers with columns [Seller, Price, Δ vs Min, PriceBot?, Delivery]. Highlight min price row and badge price bots.
    * Analytics panel: summarise avgSpread, medianSpread, maxSpread, botShare, attractivenessIndex with tooltips explaining each metric.
* Implement skeleton loaders and clean error/empty states.
* Remove any unused dependencies (e.g. Vite) from this package.
* Export buttons (CSV/XLSX/JSON) should include all fields (color, size, rating, deliveryDate, isPriceBot). Provide a toggle to exclude out-of-stock sellers if they can be detected.
──────────────────────────────────────────────────────────────────────────────
5. Documentation & testing
* Update apps/kaspi_offers_dashboard/README.md:
    * Document required env vars (DEFAULT_CITY_ID, NEXT_PUBLIC_DEFAULT_CITY_ID, KASPI_TOKEN, DEBUG_SCRAPE, PW_HEADLESS, PW_SLOWMO).
    * Explain running the dev server (pnpm dev) and the watch script (pnpm watch:prices).
    * Define metrics (median, spread, stddev, botShare, attractivenessIndex) and the price‑bot heuristic.
    * Explain city codes and how to add more.
    * Warn about scraping limitations (rate limiting, HTML changes) and suggest backoff, small concurrency, caching.
* Manual test:
    * Use master IDs 108382478 and 121207970 on cities Astana/Nur‑Sultan (710000000), Almaty (750000000), Shymkent (620000000).
    * Confirm sellers appear with correct delivery dates, variantColour, variantSize, ratings and stats. Adjust selectors if needed.
* Commit after each major milestone with clear messages.
──────────────────────────────────────────────────────────────────────────────
6. Stretch features (time permitting)
* Repricing assistant: propose a buy‑box price (maintain lowest price within a small margin) while minimizing bot retaliation.
* Inventory planner: rank which products/variants deserve stock based on rating count (demand proxy) and price spread (profit opportunity).
* Wholesale lead finder: find products with high spreads and few sellers, signalling a potential sourcing opportunity.
* Competitor watch: monitor selected sellers across SKUs, summarizing their pricing behaviour and bot intensity.
──────────────────────────────────────────────────────────────────────────────
Execution policies and stop criteria
* Follow the numbered sections strictly. Stop only when every task in sections 1–5 is complete and verified. Section 6 is optional if time allows.
* Use DEBUG_SCRAPE=1 to capture HTML/screenshots for unresolved cases; attach those artifacts to your report if relevant.
* Hard cap runtime per master product to ≈2 minutes; ensure concurrency limits are respected; close pages after use.
* After finishing, provide a short report summarizing what was changed, how you tested it, what works, and any remaining limitations.