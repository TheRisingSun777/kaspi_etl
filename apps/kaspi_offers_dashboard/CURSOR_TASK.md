You are a senior full‑stack engineer. Repository root is kaspi_etl, target app is apps/kaspi_offers_dashboard (Next.js App Router + TS + Tailwind + Playwright). Your job: repair, harden, and ship the offers dashboard and scraper; then implement analytics & exports; finalize with tests and docs. Stop only when everything in the plan is complete and validated.

High‑level intent
	•	One‑page dashboard that, given a Kaspi masterProductId + city, enumerates variants, pulls all sellers for each variant, computes stats, shows KPIs, and exports CSV/XLSX.
	•	Scraper must be reliable: correct city, open sellers tab, capture JSON if available, fall back to HTML parse, and be fast/stable.
	•	Analytics: per‑variant stats + global metrics, plus: attractivenessIndex, stabilityScore, bestEntryPrice (practical for repricing).
	•	UX: clean cards/tables, loading/error states, history of last searches, include/exclude OOS toggle.

⸻

0) Safety & project hygiene (must‑do first)
	1.	Never commit secrets. Ensure .gitignore excludes all env files. Remove any committed .env.local from git history if present. Replace with .env.example.
	•	Add comment: # KASPI_TOKEN is server-side only; never expose with NEXT_PUBLIC_.
	•	Rotate KASPI token if it ever leaked.
	2.	Add scripts:
    // package.json (in apps/kaspi_offers_dashboard)
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "typecheck": "tsc --noEmit",
    "lint": "eslint .",
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
	3.	Ensure next.config.js enables images from Kaspi if we display product images:
    /** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: { typedRoutes: true },
  images: { remotePatterns: [{ protocol: 'https', hostname: '**.kaspi.kz' }, { protocol:'https', hostname:'kaspi.kz' }] }
};
module.exports = nextConfig;
1) Type model: clean, single source of truth

Create/replace apps/kaspi_offers_dashboard/lib/types.ts with this complete version (no placeholders/ellipses):
// lib/types.ts
export type Seller = {
  name: string;
  price: number;               // in KZT
  deliveryDate?: string;       // normalized human text
  isPriceBot?: boolean;        // heuristic
};

export type Variant = {
  productId: string;           // Kaspi product (variant) ID
  label: string;               // size/variant label or fallback
  variantColor?: string;
  variantSize?: string;
  rating?: { avg?: number; count?: number };
  sellersCount: number;
  sellers: Seller[];
  stats?: {
    min?: number;
    median?: number;
    max?: number;
    spread?: number;           // max - min
    stddev?: number;
    predictedMin24h?: number;
    predictedMin7d?: number;
  };
};

export type AnalyzeResult = {
  masterProductId: string;
  productName?: string;
  cityId: string;
  productImageUrl?: string;
  attributes?: { sizesAll?: string[]; colorsAll?: string[] };
  variantMap?: Record<string, { color?: string; size?: string; name?: string }>;
  ratingCount?: number;
  variants: Variant[];

  // derived
  uniqueSellers?: number;
  analytics?: {
    avgSpread?: number;
    medianSpread?: number;
    maxSpread?: number;
    botShare?: number;                // 0..1
    attractivenessIndex?: number;     // 0..100
    stabilityScore?: number;          // 0..100
    bestEntryPrice?: number;          // suggested buy-box price
  };
};

// Back-compat aliases used by components
export type SellerInfo = Seller;
export type VariantInfo = Variant;
export type AnalyzeResponse = AnalyzeResult;
2) Analytics implementation (new file)

Add apps/kaspi_offers_dashboard/lib/analytics.ts:
import type { AnalyzeResult, Variant } from './types';

export function basicStats(nums: number[]) {
  if (!nums.length) return { min: 0, median: 0, max: 0, spread: 0, stddev: 0 };
  const sorted = [...nums].sort((a,b)=>a-b);
  const min = sorted[0];
  const max = sorted[sorted.length-1];
  const spread = max - min;
  const mid = Math.floor(sorted.length/2);
  const median = sorted.length % 2 ? sorted[mid] : (sorted[mid-1] + sorted[mid]) / 2;
  const mean = sorted.reduce((a,b)=>a+b,0)/sorted.length;
  const variance = sorted.reduce((a,b)=>a + (b-mean)*(b-mean), 0) / sorted.length;
  const stddev = Math.sqrt(variance);
  return { min, median, max, spread, stddev };
}

export function computeVariantStats(v: Variant): Variant {
  const prices = (v.sellers || []).map(s => s.price).filter(Boolean);
  const stats = basicStats(prices);
  return { ...v, sellersCount: v.sellers?.length || 0, stats };
}

export function computeGlobalAnalytics(result: AnalyzeResult): AnalyzeResult {
  const variants = result.variants.map(computeVariantStats);
  const spreads = variants.map(v => v.stats?.spread || 0).filter(n => n>0);
  const unique = new Set<string>();
  for (const v of variants) for (const s of v.sellers || []) unique.add(s.name);

  const avg = spreads.length ? spreads.reduce((a,b)=>a+b,0)/spreads.length : 0;
  const median = (() => {
    if (!spreads.length) return 0;
    const s = [...spreads].sort((a,b)=>a-b);
    const m = Math.floor(s.length/2);
    return s.length%2 ? s[m] : (s[m-1]+s[m])/2;
  })();
  const max = spreads.length ? Math.max(...spreads) : 0;

  // Heuristics
  let botCount = 0, sellerCount = 0;
  for (const v of variants) {
    sellerCount += v.sellers?.length || 0;
    for (const s of v.sellers || []) if (s.isPriceBot) botCount++;
  }
  const botShare = sellerCount ? botCount / sellerCount : 0;

  // Attractiveness: bigger spread, fewer sellers, more demand, faster delivery, less bot pressure
  // Scores are 0..1, then combined to 0..100
  const spreadScore = clamp01((avg / (median || avg || 1)));
  const scarcityScore = clamp01(1 - (unique.size / 20)); // 20 sellers = 0
  const demandScore = clamp01(Math.log10((result.ratingCount || 0) + 1) / 3); // ~0..1
  const botPenalty = clamp01(botShare); // higher = worse
  const attractivenessIndex = Math.round(
    100 * clamp01(0.45*spreadScore + 0.25*scarcityScore + 0.20*demandScore - 0.20*botPenalty)
  );

  // Stability: low relative stddev across variants is more stable
  const relStddevs = variants
    .map(v => (v.stats && v.stats.min ? (v.stats.stddev || 0) / v.stats.min : 0))
    .filter(x => Number.isFinite(x));
  const relStdAvg = relStddevs.length ? relStddevs.reduce((a,b)=>a+b,0)/relStddevs.length : 0;
  const stabilityScore = Math.round(100 * clamp01(1 - relStdAvg)); // 1-relStdAvg

  // Best entry price: undercut min by a small step; dampen if bot pressure is high
  const minAcross = Math.min(...variants.map(v => v.stats?.min || Infinity));
  const step = priceStep(minAcross);
  const botDampen = botShare > 0.35 ? step * 0.25 : step;
  const bestEntryPrice = Number.isFinite(minAcross) ? Math.max(0, Math.round((minAcross - botDampen)/10)*10) : 0;

  return {
    ...result,
    variants,
    uniqueSellers: unique.size,
    analytics: { avgSpread: round0(avg), medianSpread: round0(median), maxSpread: round0(max), botShare: round2(botShare), attractivenessIndex, stabilityScore, bestEntryPrice },
  };
}

function priceStep(p:number){ 
  if (!Number.isFinite(p)) return 50;
  if (p < 5000) return 20;
  if (p < 20000) return 50;
  if (p < 100000) return 100;
  return 200;
}
const clamp01 = (x:number)=> Math.max(0, Math.min(1, x));
const round0 = (n:number)=> Math.round(n||0);
const round2 = (n:number)=> Math.round((n||0)*100)/100;
3) Export helpers (fix broken CSV/XLSX)

Replace apps/kaspi_offers_dashboard/lib/export.ts with:
// lib/export.ts
import Papa from 'papaparse';
import * as XLSX from 'xlsx';
import type { AnalyzeResult } from './types';

function flattenRows(data: AnalyzeResult) {
  const meta = data.variantMap || {};
  const rows: Record<string, unknown>[] = [];
  for (const v of data.variants) {
    const sellers = v.sellers.length ? v.sellers : [{ name: 'Out of stock', price: 0, deliveryDate: '' }];
    for (const s of sellers) {
      rows.push({
        masterProductId: data.masterProductId,
        productName: (meta[v.productId]?.name || v.label || data.productName || '').trim(),
        variantProductId: v.productId,
        variantSize: v.variantSize || v.label || '',
        variantColor: v.variantColor || meta[v.productId]?.color || '',
        ratingAvg: v.rating?.avg ?? '',
        ratingCount: v.rating?.count ?? '',
        min: v.stats?.min ?? '',
        median: v.stats?.median ?? '',
        max: v.stats?.max ?? '',
        spread: v.stats?.spread ?? '',
        stddev: v.stats?.stddev ?? '',
        seller: s.name,
        price: s.price,
        deliveryDate: s.deliveryDate || '',
      });
    }
  }
  return rows;
}

export function exportCSV(data: AnalyzeResult): string {
  return Papa.unparse(flattenRows(data));
}

export function exportXLSX(data: AnalyzeResult): ArrayBuffer {
  const ws = XLSX.utils.json_to_sheet(flattenRows(data));
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Offers');
  return XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
}
4) API route: call scraper, then analytics

Open apps/kaspi_offers_dashboard/app/api/analyze/route.ts and fully implement the middle section (currently elided) using the analytics helpers:
import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import type { AnalyzeResult } from '@/lib/types';
import { scrapeAnalyze } from '@/server/scrape';
import { computeGlobalAnalytics } from '@/lib/analytics';

const InputSchema = z.object({
  masterProductId: z.string().min(1),
  cityId: z.string().optional(),
});

export async function POST(req: NextRequest) {
  try {
    const json = await req.json();
    const input = InputSchema.parse(json);
    const cityId = input.cityId || process.env.DEFAULT_CITY_ID || '710000000';

    const raw: AnalyzeResult = await scrapeAnalyze(input.masterProductId, cityId);
    const enriched = computeGlobalAnalytics(raw);

    return NextResponse.json(enriched, { status: 200 });
  } catch (e:any) {
    const msg = String(e?.message || '');
    const status = /429/.test(msg) ? 429 : /timeout|503/i.test(msg) ? 503 : 400;
    return NextResponse.json({ error: msg || 'Analyze failed', variants: [] }, { status });
  }
}
5) Scraper overhaul (Playwright)

Goal: robustly fetch variant seller lists for a masterProductId + cityId. Implement in apps/kaspi_offers_dashboard/server/scrape.ts. Replace any redacted code and remove .... Apply these rules:
	•	Launch a single Chromium browser; one context with desktop UA; block heavy (image, media, font) but allow CSS + JS.
	•	City control: always use URL https://kaspi.kz/shop/p/-${variantId}/?c=${cityId} and set cookie { name: 'city_id', value: cityId, domain: '.kaspi.kz', path: '/' } before navigation. After first load, verify via DOM or window config; if modal appears, set cookie again and reload.
	•	Open sellers tab: click any of texts/selectors:
	•	text: Продавцы, Все продавцы, Все предложения
	•	selectors: .sellers-tab, .sellers-table, [data-test*="sellers"]
	•	Capture network JSON: page.on('response', …) and harvest any JSON from URLs containing: api|offer|seller|price|catalog|stock|availability|listing|product.
	•	Fallback: parse HTML for seller rows; tolerant selectors:
	•	seller name: .sellers-table__merchant-name, [data-merchant-name], [class*="merchant"]
	•	price: [data-merchant-price], .sellers-table__price-cell-text, [class*="price"]
	•	delivery: .sellers-table__delivery-text, .sellers-table__delivery-price, [class*="delivery"], strings containing Постомат.
	•	Heuristics:
	•	isPriceBot: true if seller name matches /бот|bot|price bot/i OR its price equals current min price within ≤ 30 KZT and updates across ≥ 3 sellers (we have only snapshot; flag the first part; second part used once history exists).
	•	Normalize numbers from strings (\d[\d\s]+), strip spaces.
	•	Concurrency: scrape variants sequentially per masterProductId (Kaspi can be allergic to parallel hits). Limit to MAX_VARIANTS=20.
	•	Return shape: fill AnalyzeResult exactly per types.ts (including variantMap colors/sizes when discoverable).
	•	Debugging: respect DEBUG_SCRAPE=1 — save HTML (and captured JSON) under data_raw/kaspi_debug/variant_{id}.html/json for hard cases.
	•	Time limits: DEFAULT_TIMEOUT = 15_000 per page; total scrape budget ≈ 2 minutes.
	•	Close pages after each variant; close browser at the end.

Also add a tiny in-memory LRU cache (5 minutes) keyed by {masterProductId}:{cityId} to avoid hammering the site when the user toggles settings. Add apps/kaspi_offers_dashboard/server/cache.ts:
// server/cache.ts
type Entry<T> = { v: T; t: number };
const store = new Map<string, Entry<any>>();
const TTL = 5 * 60 * 1000;

export function getCached<T>(k:string): T | null {
  const e = store.get(k);
  if (!e) return null;
  if (Date.now() - e.t > TTL) { store.delete(k); return null; }
  return e.v as T;
}
export function setCached<T>(k:string, v:T){ store.set(k, { v, t: Date.now() }); }
Use it in scrapeAnalyze (get → return; else fetch → set).

⸻

6) UI fixes and polish
	1.	SearchBar.tsx: fix Shymkent ID (was wrong).
    const DEFAULT_CITY_ID = process.env.NEXT_PUBLIC_DEFAULT_CITY_ID || '710000000';
// Shymkent is 620000000
// Options:
<option value="710000000">Astana / Nur-Sultan</option>
<option value="750000000">Almaty</option>
<option value="620000000">Shymkent</option>
Keep a localStorage history (last 5 masterProductIds) — if already implemented, ensure it works.

	2.	KpiCards.tsx: remove any ... remnants; show:
	•	Product Name
	•	Total Variants
	•	Total Sellers (unique)
	•	Fastest Delivery (min string across all sellers)
	•	Attractiveness (from analytics.attractivenessIndex)
	3.	VariantCard.tsx & SellersTable.tsx:
	•	Ensure no ... placeholders remain.
	•	For Δ vs Min, compute difference vs the variant min; color it green (min), gray otherwise.
	•	Badge for isPriceBot.
	4.	app/page.tsx:
	•	Implement includeOOS toggle to hide variants with no sellers (or sellers with price=0) from the grid and from export.
	•	Hook up export buttons:
    import { exportCSV, exportXLSX } from '@/lib/export';
// CSV
const csv = exportCSV(filtered);
const csvBlob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
// XLSX
const xbuf = exportXLSX(filtered);
const xblob = new Blob([xbuf], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
	•	Copy JSON button: stringify AnalyzeResult with 2-space indent.

	5.	globals.css/tailwind.config.ts: remove ...; ensure classes used above exist. Keep dark mode.

⸻

7) API surface contract & validation
	•	Input: { masterProductId: string; cityId?: string }
	•	Output: AnalyzeResult per types.ts
	•	Guardrail: return 400 on Zod validation errors, 429 for rate‑limited, 503 on timeouts; always include { variants: [] } on error so UI won’t crash.

⸻

8) Tests (Vitest + fixtures)

Create a small fixture‑based parser test that doesn’t hit the network:
	•	Put 2–3 HTML files from data_raw/kaspi_debug/ into apps/kaspi_offers_dashboard/test/fixtures/.
	•	Expose a pure function parseSellersFromHtml(html: string) from server/scrape.ts (or move it to server/parse.ts) and unit‑test:
	•	Extract ≥ 1 seller with name + price
	•	Prices parsed correctly from formatted strings
	•	Delivery text found when present
	•	Test lib/analytics.ts with synthetic variants.

⸻

9) Documentation

Update apps/kaspi_offers_dashboard/README.md:
	•	Install (pnpm), run, env vars (DEFAULT_CITY_ID, NEXT_PUBLIC_DEFAULT_CITY_ID, KASPI_TOKEN, DEBUG_SCRAPE).
	•	Example masterProductIds for smoke tests: 108382478, 121207970.
	•	Explain metrics (attractiveness, stability, bestEntry) with formulas and caveats.
	•	Security note: server‑side token only.

⸻

10) Acceptance criteria (do not stop until all pass)
	•	pnpm typecheck passes, no ... left in TS files.
	•	pnpm build succeeds.
	•	pnpm test passes.
	•	Manual run: enter 108382478 in Astana, see variants list with sellers, non‑zero spreads, exports working, and analytics populated.
	•	Switching city changes sellers (URL ?c=cityId enforced) and data reflects city.
	•	DEBUG_SCRAPE=1 saves artifacts for one variant on demand.
	•	LRU cache reduces repeat latency noticeably within 5 minutes.
	•	README updated.

⸻

Helpful tips for future DOM/API changes (keep in code comments)
	•	Keep selectors plural and tolerant; always try multiple options.
	•	Prefer captured JSON when present; otherwise DOM parse; keep both paths alive.
	•	Avoid parallel hammering; Kaspi will throttle quickly.
	•	Bots tend to mirror the min price; avoid undercutting by big steps — we use small priceStep() and round to tens to avoid churn.
	•	If seller list collapses to 0, reload once with city cookie + ?c= param again, then bail with a helpful error.

⸻

Final deliverable

When complete, output:
	1.	A short engineering report: what was broken, what you changed, and how you validated it.
	2.	Commands to run locally.
	3.	Any remaining limitations or TODOs.

Stop only when all steps above are finished and verified.