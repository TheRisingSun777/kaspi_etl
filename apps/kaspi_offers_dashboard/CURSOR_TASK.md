You are a senior full‑stack engineer. Repo root: kaspi_etl. App: apps/kaspi_offers_dashboard (Next.js App Router + TypeScript + Tailwind + Playwright).
Goal: finalize the Offers dashboard, then add a Pricebot section that manages our store’s active offers and auto‑reprices within min/max guardrails.
Do not stop until all acceptance criteria at the bottom are green.
Environment (local only):
KASPI_MERCHANT_ID=30141222
KASPI_MERCHANT_API_BASE=https://mc.shop.kaspi.kz
KASPI_MERCHANT_API_KEY=<keep in .env.local, never commit>
# optional cookie fallback if API key flow is limited; paste mc-session and mc-sid from your browser
KASPI_MERCHANT_COOKIES=mc-session=...; mc-sid=...
# local admin token to guard write endpoints
LOCAL_ADMIN_TOKEN=dev-only-strong-random
# feature flags
PW_HEADLESS=1
PW_SLOWMO=0
DEBUG_SCRAPE=0
SCRAPE_MAX_TABS=1
SCRAPE_CONCURRENCY=1
SCRAPE_TTL_SEC=180
Ground rules stay the same as before: TypeScript‑strict, small commits, never log credentials, close Playwright contexts/tabs, and work only in apps/kaspi_offers_dashboard (plus minimal root config if required).

3) Pricebot engine + scheduler + APIs (server only)

Goal: make the “Pricebot (Store 30141222)” section show real offers and let me set min/max/step/interval, view opponents, ignore sellers, and reprice via Merchant endpoints.

3.1 Project structure (create these)
apps/kaspi_offers_dashboard/
  lib/merchant/
    client.ts
    auth.ts
  lib/pricebot/
    settings.ts
    engine.ts
    opponents.ts
    runner.ts
  app/api/pricebot/
    offers/route.ts
    opponents/route.ts
    settings/route.ts
    reprice/route.ts
  app/api/debug/
    merchant/route.ts
    If a folder doesn’t exist, create it. All routes are server code only (export const dynamic='force-dynamic'), guarded by LOCAL_ADMIN_TOKEN for writes.

3.2 Merchant auth + HTTP (server)

lib/merchant/auth.ts
	•	Export buildAuthHeaders(): Record<string,string>:
	•	If KASPI_MERCHANT_API_KEY set → return { 'x-auth-version': '3', 'Authorization': 'Bearer ' + apiKey } (or just pass through API key header variant you already used in /api/pricebot/reprice that returned 200 OK).
	•	Else if KASPI_MERCHANT_COOKIES set → return { cookie: process.env.KASPI_MERCHANT_COOKIES }.
	•	Never log the key/cookies.

lib/merchant/client.ts
	•	Export:
	•	async function fetchJSON(path: string, init?: RequestInit)
	•	async function getOffersPage(page=0, limit=100)
	•	GET ${base}/bff/offer-view/list?m=${merchantId}&p=${page}&l=${limit}&a=true&lowStock=false&notSpecifiedStock=false
	•	async function getOfferDetailsBySku(sku: string)
	•	GET ${base}/bff/offer-view/details?m=${merchantId}&s=${encodeURIComponent(sku)}
	•	async function postDiscount(body: { merchantUID: string; merchantSKU: string; entries: { city: string; price: number }[] })
	•	POST ${base}/price/trends/api/v1/mc/discount with JSON body (this is the one you captured; payload shape matches your DevTools payload).
	•	fetchJSON should:
	•	Merge buildAuthHeaders()
	•	Set Accept: application/json
	•	Throw rich errors on 401/403 (tell the UI “Missing Merchant credentials”).
	•	Notes:
	•	If API key returns 401 for listing endpoints, automatically fallback to cookie mode.
	•	Add tiny jitter delays to avoid anti‑bot.

3.3 Settings store (min/max/step/interval/ignore)

lib/pricebot/settings.ts
	•	Keep it simple: local JSON file at data/pricebot/settings.json (create folder data/pricebot under the app root). No DB yet.
	•	Types:
    export type PricebotSetting = {
  sku: string;               // merchant SKU (e.g., CL_OC_MEN_…)
  productId?: string;        // resolved from details
  minPrice?: number;
  maxPrice?: number;
  stepKzt?: number;          // default 1
  scanIntervalMin?: number;  // 1..10, default 3
  active?: boolean;          // default false
  ignoreSellers?: string[];  // exact names to skip
  lastSeenPrice?: number;    // telemetry
  updatedAt: string;
}
	•	Export CRUD:
	•	getSettings(): Promise<PricebotSetting[]>
	•	getSetting(sku: string)
	•	upsertSetting(partial: PricebotSetting)
	•	removeSellerIgnore(sku, seller)
	•	Ensure atomic writes (write temp file then rename).

3.4 Opponents service (uses your scraper or BFF details → productId)

lib/pricebot/opponents.ts
	•	Export:
	•	async function resolveProductIdForSku(sku: string): Promise<string> → via getOfferDetailsBySku(sku) (you already captured a working GET that returned 200 OK in DevTools), pick the productId from JSON.
	•	async function listOpponentsByProduct(productId: string, cityId: string):
	•	Call existing scraper/analyzer (scrapeAnalyze(productId, cityId)) and flatten sellers for the selected variant (one productId each). Return { seller, price }[] sorted ASC.
	•	Respect ignoreSellers by filtering.

3.5 Engine (decide a new price that respects min/max/step)

lib/pricebot/engine.ts
	•	Export:
	•	computeNextPrice({ ourPrice, opponents, minPrice, maxPrice, stepKzt }): number
	•	If opponents empty → clamp to maxPrice (or keep ourPrice if inside range).
	•	Otherwise target min(opponents.price) - stepKzt. Clamp to [minPrice, maxPrice].
	•	Round to integer KZT.
	•	async function repriceOnce({ sku, cityId }): Promise<{ newPrice:number, applied:boolean, reason?:string }>
	•	Load setting; resolve productId; list opponents; compute next; if next == ourPrice → return applied:false, reason:'no-change'.
	•	Call postDiscount with:
    {
  "merchantUID": "30141222",
  "merchantSKU": "<sku>",
  "entries": [{ "city": "<cityId>", "price": <newPrice> }]
}
(This mirrors the /price/trends/api/v1/mc/discount request you captured and successfully replayed.)

	•	If API responds “NOT_ENOUGH_HISTORY” → return applied:false, reason:'NOT_ENOUGH_HISTORY' (bubble to UI).

3.6 API routes

All routes live under app/api/pricebot/* and return JSON; protect POST with Authorization: Bearer ${LOCAL_ADMIN_TOKEN}.
	•	GET /api/pricebot/offers
	•	Merge: getOffersPage() (loop pages until empty), each item ⇒ { name, sku, productId, price, city:'710000000' }.
	•	Join with settings; include opponentsCount by calling listOpponentsByProduct(productId, city) only when ?withOpponents=true to keep it fast.
	•	If 401 from Merchant, return { ok:false, error:'UNAUTHORIZED' }.
	•	GET /api/pricebot/opponents?sku=...&cityId=710000000
	•	Resolve productId; return [{ seller, price }] sorted ASC.
	•	POST /api/pricebot/settings
	•	Body: { sku, minPrice, maxPrice, stepKzt, scanIntervalMin, active, ignoreSellers }
	•	Upsert and return full setting.
	•	POST /api/pricebot/reprice
	•	Body: { sku, cityId, price? }
	•	If price provided → call postDiscount directly.
	•	Else → call repriceOnce (engine) which computes then posts.
	•	Return full engine decision + raw merchant response.
	•	This route already responded 200 OK for you; keep the success path and upgrade to use postDiscount.
	•	GET /api/debug/merchant
	•	Call getOffersPage(0) and return { ok: true } if status 200, else { ok:false, status }.
	•	This replaces the old version that returned 401.

3.7 Scheduler (server runner)

lib/pricebot/runner.ts
	•	A singleton runner (store on globalThis.__pricebotRunner) that:
	•	Loads all settings where active=true.
	•	For each, sets a setInterval based on scanIntervalMin (clamped 1..10).
	•	On tick: call repriceOnce({ sku, cityId:'710000000' }).
	•	Log compact line per tick: SKU ... min/max/step → nextPrice ..., result: applied|reason.
	•	Only start the runner on the server when process.env.NODE_ENV !== 'test'.
	•	Expose tiny dev control:
	•	GET /api/pricebot/runner/status → list tasks + next run at.
	•	POST /api/pricebot/runner/reload (guarded) → reload settings, restart timers.

⸻

4) Pricebot UI (second section) — finish and wire

Update the existing “Pricebot (Store 30141222)” card so it loads data (it currently shows “No offers found…”, which came from a placeholder in your static dump). Then implement inline editing + opponent drawer.  ￼

Files to touch
	•	app/page.tsx (or the component where the Pricebot card lives)
	•	components/pricebot/PricebotTable.tsx (create)
	•	components/pricebot/OpponentsDrawer.tsx (create)
	•	components/ui/* tiny inputs/toggles if needed

Behavior
	•	On mount, fetch GET /api/pricebot/offers.
	•	Render rows:
	•	Name, Variant Product ID (from details), Our Price, Min (input), Max (input), Step (input), Interval (1–10 min), Active (toggle), Opponents (a link with a number).
	•	Opponents link opens <OpponentsDrawer>:
	•	Loads GET /api/pricebot/opponents?sku=...&cityId=710000000.
	•	Shows sellers with current price (ASC). Each has an “ignore” toggle that updates ignoreSellers via POST /api/pricebot/settings.
	•	“Run” button per row:
	•	Calls POST /api/pricebot/reprice with { sku, cityId:'710000000' } (engine path).
	•	On success, toast the result (applied vs reason).
	•	Persist inline edits with debounce (600ms) to POST /api/pricebot/settings.
	•	Empty/error states:
	•	If /offers returns UNAUTHORIZED, show “Add Merchant credentials in .env.local” with a link to docs. (The HTML dump you saved showed this empty state earlier; replace it with live data.)  ￼

⸻

5) Price watch script (CLI)

Augment the earlier watch plan so it can also dump per‑tick deltas for any list of productIds (not SKUs).

scripts/price_watch.ts
	•	CLI: --ids=108382478,121207970 --city=710000000 --intervalSec=300
	•	Each tick: call scrapeAnalyze(id, city), append NDJSON to data_raw/watch/<id>.ndjson:
    {"ts":"2025-08-10T12:34:56Z","variantId":"121207970","seller":"ShopKZ","price":2810,"isPriceBot":false}
    	•	Keep sliding window per (variantId, seller) and flag bots that repeatedly undercut by ≤1 KZT.
	•	Add npm script: "watch:prices": "tsx scripts/price_watch.ts --ids=108382478,121207970 --city=710000000 --intervalSec=300"

⸻

6) Analytics polish (dashboard)
	•	In the Analytics card, include avgSpread, medianSpread, maxSpread, botShare, attractivenessIndex (already specified in Steps 1–2).
	•	For each VariantCard and SellersTable, show “Δ vs Min” and PriceBot? (already reflected in your HTML dumps; keep it consistent).  ￼  ￼

⸻

7) City‑aware delivery (verify end‑to‑end)
	•	Make sure scraped delivery dates reflect the selected city (710000000, 750000000, 620000000).
	•	Add a small city switcher cached to localStorage.
	•	Surface Fastest Delivery KPI.

⸻

8) Reliability & perf
	•	LRU cache (TTL via SCRAPE_TTL_SEC) at scraper layer.
	•	Backoff on anti‑bot signs; randomize small delays (100–400ms).
	•	Always close pages/contexts/browsers. Cap to 1 tab unless SCRAPE_MAX_TABS=2.
	•	In pricebot engine, guard against rapid flapping: don’t reprice again if last post was <30s ago.

⸻

9) Docs & safety

README.md (inside the app)
	•	Add Pricebot section:
	•	How to set .env.local values (API key or cookie fallback).
	•	Security note: .env.local is git‑ignored.
	•	How to start runner, how to stop (/api/pricebot/runner/reload).
	•	How opponents list is built (BFF details → productId → scraper sellers).
	•	Add “Troubleshooting”:
	•	401 on /api/debug/merchant → missing/invalid credentials.
	•	NOT_ENOUGH_HISTORY on reprice → show first suitable date (your successful cURL returned this; bubble it to UI).

⸻

10) Tests & quick validation
	•	Add minimal unit tests for computeNextPrice() and settings.ts (file read/write).
	•	Manual checks:
	•	/api/debug/merchant returns { ok:true } once creds are set.
	•	/api/pricebot/offers returns live rows; the table is not empty anymore (replaces prior placeholder).  ￼
	•	Opponents drawer shows sorted sellers and “ignore” toggles work.
	•	POST /api/pricebot/reprice works both with explicit price and with engine compute (you already saw 200 OK with NOT_ENOUGH_HISTORY; show that in UI).
	•	Runner status shows scheduled tasks.

⸻

File‑by‑file stubs (keep tight; fill in logic)

app/api/pricebot/offers/route.ts
import { NextResponse } from 'next/server';
import { getOffersPage } from '@/lib/merchant/client';
import { getSettings } from '@/lib/pricebot/settings';

export const dynamic = 'force-dynamic';

export async function GET(req: Request) {
  try {
    const url = new URL(req.url);
    const withOpponents = url.searchParams.get('withOpponents') === 'true';
    const all: any[] = [];
    let page = 0;
    for (;;) {
      const res = await getOffersPage(page, 100);
      if (!res?.items?.length) break;
      all.push(...res.items);
      page++;
    }
    const settings = await getSettings();
    // map + merge minimal fields here; compute opponentsCount later if requested
    return NextResponse.json({ ok: true, items: all, settings });
  } catch (e: any) {
    const status = e?.status ?? 500;
    return NextResponse.json({ ok: false, error: e?.message ?? 'ERR', status });
  }
}

app/api/pricebot/opponents/route.ts
import { NextResponse } from 'next/server';
import { resolveProductIdForSku, listOpponentsByProduct } from '@/lib/pricebot/opponents';

export const dynamic = 'force-dynamic';

export async function GET(req: Request) {
  const url = new URL(req.url);
  const sku = url.searchParams.get('sku')!;
  const cityId = url.searchParams.get('cityId') || '710000000';
  const productId = await resolveProductIdForSku(sku);
  const list = await listOpponentsByProduct(productId, cityId);
  return NextResponse.json({ ok: true, productId, opponents: list });
}

app/api/pricebot/settings/route.ts
import { NextResponse } from 'next/server';
import { upsertSetting } from '@/lib/pricebot/settings';

export async function POST(req: Request) {
  const auth = req.headers.get('authorization') || '';
  if (!auth.endsWith(process.env.LOCAL_ADMIN_TOKEN!)) {
    return NextResponse.json({ ok:false, error:'UNAUTHORIZED' }, { status:401 });
  }
  const body = await req.json();
  const saved = await upsertSetting(body);
  return NextResponse.json({ ok: true, setting: saved });
}

app/api/pricebot/reprice/route.ts
import { NextResponse } from 'next/server';
import { repriceOnce } from '@/lib/pricebot/engine';
import { postDiscount } from '@/lib/merchant/client';

export async function POST(req: Request) {
  const auth = req.headers.get('authorization') || '';
  if (!auth.endsWith(process.env.LOCAL_ADMIN_TOKEN!)) {
    return NextResponse.json({ ok:false, error:'UNAUTHORIZED' }, { status:401 });
  }
  const { sku, cityId = '710000000', price } = await req.json();
  if (price != null) {
    const res = await postDiscount({ merchantUID: process.env.KASPI_MERCHANT_ID!, merchantSKU: sku, entries: [{ city: cityId, price }] });
    return NextResponse.json({ ok: true, mode:'direct', result: res });
  }
  const decision = await repriceOnce({ sku, cityId });
  return NextResponse.json({ ok: true, mode:'engine', ...decision });
}

app/api/debug/merchant/route.ts
import { NextResponse } from 'next/server';
import { getOffersPage } from '@/lib/merchant/client';

export const dynamic = 'force-dynamic';
export async function GET() {
  try {
    await getOffersPage(0, 10);
    return NextResponse.json({ ok: true });
  } catch (e:any) {
    return NextResponse.json({ ok:false, status:e?.status ?? 500, sample:'' });
  }
}
Keep component code terse; use existing design tokens (Inter, Apple‑ish palette) from earlier steps.

Commit plan (small, reviewable)
	1.	feat(pricebot): merchant client (API key/cookie) + debug route
	2.	feat(pricebot): settings store (JSON) + types
	3.	feat(pricebot): opponents resolver (details→product) + scraper bridge
	4.	feat(pricebot): engine (computeNextPrice, repriceOnce)
	5.	feat(api): /pricebot/offers | /opponents | /settings | /reprice
	6.	feat(ui): PricebotTable + OpponentsDrawer wired
	7.	feat(runner): scheduler singleton + status/reload endpoints
	8.	docs: README pricebot setup + troubleshooting
	9.	test: engine + settings

⸻

Don’t stop until this checklist is green
	•	/api/debug/merchant → { ok:true } locally when creds present.
	•	“Pricebot (Store 30141222)” renders real offers (no more “No offers found”).  ￼
	•	I can set min/max/step/interval per row and toggle Active; values persist.
	•	“Opponents” link shows sellers sorted by price ASC with ignore toggles.
	•	Clicking Run posts a reprice:
	•	If merchant responds NOT_ENOUGH_HISTORY, UI shows the firstSuitableDate you already saw in your curl (don’t hide it).
	•	Runner is on; status endpoint lists tasks; intervals respected (1..10 min).
	•	Docs updated with env + cookies fallback, and safety notes.

Only stop when everything above is done and the UI shows real data.