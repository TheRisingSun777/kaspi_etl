# Agent Ops (non‑blocking)
- Do not pause for summaries or confirmations between steps.
- Apply patches and run shell/git commands autonomously.
- If port 3000 is busy, automatically use 3001 (`PORT=3001`) and keep going.
- If a shell command fails, retry once with a safe fallback; otherwise log to CURSOR_PROGRESS.md and continue.
- Only stop when every checklist item and acceptance criterion is green.

## Pre‑flight
- If `lsof -ti tcp:3000` returns a PID, kill it or run dev as `PORT=3001`.
- For MC calls: if `/api/debug/merchant` returns 401, skip tests that require MC and log “REFRESH COOKIE”, then proceed with non‑MC tasks. Resume MC tests after cookie is refreshed.

You are working in a monorepo. Target app:
apps/kaspi_offers_dashboard

GOAL
Wire up the Kaspi Merchant (MC) data path and complete the Pricebot dashboard so it actually lists my live offers for merchant 30141222, lets me set min/max/step/interval, shows competitors with an ignore knob, and triggers repricing via MC’s discount endpoint. Add a robust MC client, a debug route, storage for Pricebot settings, and replace the PricebotPanel UI. Do not expose credentials. Stop only when ALL tasks in this plan are done and the UI renders real offers.

CONSTRAINTS
- Next.js App Router (server routes in app/api/**/route.ts).
- Credentials only via .env.local (never check in).
- KASPI_MERCHANT_AUTH_MODE=cookie, use KASPI_MERCHANT_COOKIE.
- Always send MC headers: Origin https://kaspi.kz, Referer https://kaspi.kz, x-auth-version 3, Accept-Language ru-RU, realistic User-Agent.
- Encode all SKUs with encodeURIComponent before placing into URLs.

PHASE A — MC CLIENT + DEBUG
1) Create file: apps/kaspi_offers_dashboard/lib/kaspi/client.ts with a small typed client:

---------------------------------- FILE: lib/kaspi/client.ts
/* eslint-disable @typescript-eslint/no-explicit-any */
const BASE = process.env.KASPI_MERCHANT_API_BASE || 'https://mc.shop.kaspi.kz';
const AUTH_MODE = process.env.KASPI_MERCHANT_AUTH_MODE || 'cookie';

function authHeaders() {
  if (AUTH_MODE === 'cookie') {
    const cookie = process.env.KASPI_MERCHANT_COOKIE;
    if (!cookie) throw new Error('KASPI_MERCHANT_COOKIE is missing');
    return { Cookie: cookie };
  }
  const key = process.env.KASPI_MERCHANT_API_KEY;
  if (!key) throw new Error('KASPI_MERCHANT_API_KEY is missing');
  return { Authorization: `Bearer ${key}` };
}

export function getMerchantId(): string {
  const m = process.env.KASPI_MERCHANT_ID;
  if (!m) throw new Error('KASPI_MERCHANT_ID is missing');
  return m;
}

export async function mcFetch(path: string, init: RequestInit = {}) {
  const url = `${BASE}${path}`;
  const headers = {
    accept: 'application/json, text/plain, */*',
    'content-type': 'application/json',
    origin: 'https://kaspi.kz',
    referer: 'https://kaspi.kz/',
    'x-auth-version': '3',
    'accept-language': 'ru-RU,ru;q=0.9',
    'user-agent':
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari',
    ...authHeaders(),
    ...(init.headers || {}),
  } as Record<string, string>;

  const res = await fetch(url, { ...init, headers, cache: 'no-store', redirect: 'follow' });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`Kaspi MC ${res.status}: ${text.slice(0, 500)}`);
  }
  return res;
}
----------------------------------

2) Create debug endpoint: apps/kaspi_offers_dashboard/app/api/debug/merchant/route.ts

---------------------------------- FILE: app/api/debug/merchant/route.ts
import { NextResponse } from 'next/server';
import { mcFetch, getMerchantId } from '@/lib/kaspi/client';

export async function GET() {
  try {
    const m = getMerchantId();
    const res = await mcFetch(`/offers/api/v1/offer/count?m=${m}`);
    const data = await res.json();
    return NextResponse.json({ ok: true, status: 200, data });
  } catch (e: any) {
    const msg = (e && e.message) || 'unknown';
    const status = msg.includes('401') ? 401 : 500;
    return NextResponse.json({ ok: false, status, error: msg }, { status });
  }
}
----------------------------------

PHASE B — MERCHANT OFFERS + DETAILS
3) Implement offers list: apps/kaspi_offers_dashboard/app/api/merchant/offers/route.ts
Call MC “bff” list and normalize. Default page=0 limit=50 available=true.

---------------------------------- FILE: app/api/merchant/offers/route.ts
import { NextResponse } from 'next/server';
import { mcFetch, getMerchantId } from '@/lib/kaspi/client';

type OfferRow = {
  sku: string;           // merchant SKU
  productId: number;     // variant product id
  name: string;
  price: number;         // our price in city DEFAULT_CITY_ID if present, else 0
};

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const p = Number(searchParams.get('p') ?? '0');
  const l = Number(searchParams.get('l') ?? '50');
  const m = getMerchantId();

  const url = `/bff/offer-view/list?m=${m}&p=${p}&l=${l}&a=true&t=&c=&lowStock=false&notSpecifiedStock=false`;
  const res = await mcFetch(url);
  const json = await res.json();

  // json shape may differ; be defensive
  const items: any[] = json?.items || json?.content || json || [];
  const rows: OfferRow[] = items.map((it: any) => {
    const sku = it.merchantSku || it.sku || it.offerSku || it.id || '';
    const productId = Number(it.variantProductId || it.productId || it.variantId || 0);
    const name = it.name || it.title || it.productName || '';
    const price = Number(it.price || it.currentPrice || it.ourPrice || 0);
    return { sku, productId, name, price };
  }).filter(r => r.sku);

  return NextResponse.json({ ok: true, items: rows });
}
----------------------------------

4) Implement offer details (competitors): apps/kaspi_offers_dashboard/app/api/merchant/offer/[sku]/route.ts

---------------------------------- FILE: app/api/merchant/offer/[sku]/route.ts
import { NextResponse } from 'next/server';
import { mcFetch, getMerchantId } from '@/lib/kaspi/client';

export async function GET(
  _req: Request,
  { params }: { params: { sku: string } }
) {
  const m = getMerchantId();
  const sku = decodeURIComponent(params.sku);
  const url = `/bff/offer-view/details?m=${m}&s=${encodeURIComponent(sku)}`;
  const res = await mcFetch(url);
  const data = await res.json();

  // Normalize sellers list minimally
  const sellers = (data?.sellers || data?.offers || []).map((s: any) => ({
    name: s?.sellerName || s?.name || '',
    price: Number(s?.price || s?.value || 0),
    isBot: !!(s?.bot || s?.priceBot || false),
  }));

  return NextResponse.json({
    ok: true,
    product: data?.product || data?.model || null,
    sellers,
  });
}
----------------------------------

PHASE C — PRICEBOT STORAGE
5) Create local settings store: apps/kaspi_offers_dashboard/lib/pricebot/storage.ts

---------------------------------- FILE: lib/pricebot/storage.ts
import fs from 'fs';
import path from 'path';

export type BotSettings = {
  min: number;
  max: number;
  step: number;
  interval: number; // minutes [1..10]
  active: boolean;
  ignoreSellers: string[];
};

type Store = Record<string, BotSettings>; // key = sku

const FILE = path.join(process.cwd(), 'apps', 'kaspi_offers_dashboard', 'server', 'db', 'pricebot.json');

function ensureDir() {
  const dir = path.dirname(FILE);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

export function readStore(): Store {
  try {
    const raw = fs.readFileSync(FILE, 'utf-8');
    return JSON.parse(raw) as Store;
  } catch {
    return {};
  }
}

export function writeStore(st: Store) {
  ensureDir();
  fs.writeFileSync(FILE, JSON.stringify(st, null, 2));
}

export function getSettings(sku: string): BotSettings {
  const st = readStore();
  return st[sku] || { min: 0, max: 0, step: 1, interval: 5, active: false, ignoreSellers: [] };
}

export function upsertSettings(sku: string, patch: Partial<BotSettings>) {
  const st = readStore();
  const cur = st[sku] || { min: 0, max: 0, step: 1, interval: 5, active: false, ignoreSellers: [] };
  st[sku] = { ...cur, ...patch };
  writeStore(st);
  return st[sku];
}

export function toggleIgnore(sku: string, seller: string, ignore: boolean) {
  const st = readStore();
  const cur = st[sku] || { min: 0, max: 0, step: 1, interval: 5, active: false, ignoreSellers: [] };
  const set = new Set(cur.ignoreSellers);
  if (ignore) set.add(seller); else set.delete(seller);
  st[sku] = { ...cur, ignoreSellers: Array.from(set) };
  writeStore(st);
  return st[sku];
}
----------------------------------

6) Merge MC offers with settings: apps/kaspi_offers_dashboard/app/api/pricebot/offers/route.ts

---------------------------------- FILE: app/api/pricebot/offers/route.ts
import { NextResponse } from 'next/server';
import { getMerchantId, mcFetch } from '@/lib/kaspi/client';
import { getSettings } from '@/lib/pricebot/storage';

export async function GET() {
  const m = getMerchantId();
  const res = await mcFetch(`/bff/offer-view/list?m=${m}&p=0&l=50&a=true&t=&c=&lowStock=false&notSpecifiedStock=false`);
  const json = await res.json();
  const items: any[] = json?.items || json?.content || [];

  const rows = items.map((it: any) => {
    const sku = it.merchantSku || it.sku || it.offerSku || it.id || '';
    if (!sku) return null;
    const settings = getSettings(sku);
    return {
      sku,
      productId: Number(it.variantProductId || it.productId || 0),
      name: it.name || it.title || '',
      price: Number(it.price || it.currentPrice || 0),
      settings,
      opponents: Number(it.sellersCount || it.opponents || 0),
    };
  }).filter(Boolean);

  return NextResponse.json({ ok: true, items: rows });
}
----------------------------------

7) Settings update routes:

---------------------------------- FILE: app/api/pricebot/settings/[sku]/route.ts
import { NextResponse } from 'next/server';
import { upsertSettings } from '@/lib/pricebot/storage';

export async function PATCH(request: Request, { params }: { params: { sku: string } }) {
  const body = await request.json();
  const sku = decodeURIComponent(params.sku);
  const updated = upsertSettings(sku, body);
  return NextResponse.json({ ok: true, sku, settings: updated });
}
----------------------------------

---------------------------------- FILE: app/api/pricebot/ignore-seller/route.ts
import { NextResponse } from 'next/server';
import { toggleIgnore } from '@/lib/pricebot/storage';

export async function POST(request: Request) {
  const { sku, seller, ignore } = await request.json();
  const updated = toggleIgnore(sku, seller, !!ignore);
  return NextResponse.json({ ok: true, sku, settings: updated });
}
----------------------------------

PHASE D — REPRICE (DISCOUNT) ENDPOINT (ensure it exists & solid)
8) Ensure: apps/kaspi_offers_dashboard/app/api/pricebot/reprice/route.ts

---------------------------------- FILE: app/api/pricebot/reprice/route.ts
import { NextResponse } from 'next/server';
import { getMerchantId, mcFetch } from '@/lib/kaspi/client';

export async function POST(request: Request) {
  const { sku, price, cityId } = await request.json();
  if (!sku || !price || !cityId) {
    return NextResponse.json({ ok: false, status: 400, error: 'sku, price, cityId are required' }, { status: 400 });
  }
  const m = getMerchantId();
  const payload = {
    merchantUID: String(m),
    merchantSKU: String(sku),
    entries: [{ city: String(cityId), price: Number(price) }],
  };
  const res = await mcFetch('/price/trends/api/v1/mc/discount', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  return NextResponse.json({ ok: true, result: Array.isArray(data) ? data : [data] });
}
----------------------------------

PHASE E — PRICEBOT UI
9) Replace PricebotPanel with a wired version.
File: apps/kaspi_offers_dashboard/components/PricebotPanel.tsx
- Loads /api/pricebot/offers
- Edits per-row settings (PATCH to /api/pricebot/settings/[sku])
- “Opponents (N)” opens a modal → fetch /api/merchant/offer/[sku], shows sellers sorted asc by price with an ignore knob per seller (POST /api/pricebot/ignore-seller).
- “Run” calls POST /api/pricebot/reprice with { sku, price, cityId: process.env.NEXT_PUBLIC_DEFAULT_CITY_ID }.
- “Run All” runs for rows where settings.active===true with 1s delay between calls.

Implement a simple version without external UI libs; keep current styling classes.

---------------------------------- FILE: components/PricebotPanel.tsx
'use client';

import { useEffect, useState } from 'react';

type Row = {
  sku: string;
  productId: number;
  name: string;
  price: number;
  opponents: number;
  settings: {
    min: number;
    max: number;
    step: number;
    interval: number;
    active: boolean;
    ignoreSellers: string[];
  }
};

export default function PricebotPanel() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState<{ sku: string, sellers: { name: string, price: number, isBot: boolean }[] } | null>(null);
  const cityId = process.env.NEXT_PUBLIC_DEFAULT_CITY_ID || '710000000';

  async function load() {
    setLoading(true);
    try {
      const r = await fetch('/api/pricebot/offers', { cache: 'no-store' });
      const j = await r.json();
      setRows(j.items || []);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function saveSettings(sku: string, patch: Partial<Row['settings']>) {
    const r = await fetch(`/api/pricebot/settings/${encodeURIComponent(sku)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    });
    const j = await r.json();
    setRows(prev => prev.map(x => x.sku === sku ? { ...x, settings: j.settings } : x));
  }

  async function toggleIgnore(sku: string, seller: string, ignore: boolean) {
    await fetch('/api/pricebot/ignore-seller', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sku, seller, ignore }),
    });
    // no strict reload; just mutate local sellers + settings
    if (modal?.sku === sku) {
      setModal({
        sku,
        sellers: modal.sellers.map(s => s.name === seller ? { ...s } : s),
      });
    }
  }

  async function openOpponents(sku: string) {
    const r = await fetch(`/api/merchant/offer/${encodeURIComponent(sku)}`);
    const j = await r.json();
    const sellers = (j.sellers || []).sort((a: any, b: any) => (a.price ?? 0) - (b.price ?? 0));
    setModal({ sku, sellers });
  }

  async function reprice(sku: string, price: number) {
    const r = await fetch('/api/pricebot/reprice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sku, price, cityId }),
    });
    const j = await r.json();
    if (j?.ok && Array.isArray(j.result) && j.result[0]?.rejectReason) {
      alert(`Reprice response: ${j.result[0].rejectReason}${j.result[0].firstSuitableDate ? ' (firstDate ' + j.result[0].firstSuitableDate + ')' : ''}`);
    }
  }

  async function runAll() {
    for (const row of rows) {
      if (!row.settings.active) continue;
      let target = row.price;
      // naive policy: undercut min seller by step within [min..max]
      target = Math.max(row.settings.min || 0, Math.min(row.settings.max || Infinity, row.price));
      await reprice(row.sku, target);
      await new Promise(r => setTimeout(r, 1000));
    }
  }

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm text-gray-500">Pricebot (Store {process.env.NEXT_PUBLIC_STORE_ID || '30141222'})</div>
        <div className="flex gap-2">
          <button className="btn-outline" onClick={load} disabled={loading}>Reload</button>
          <button className="btn-outline" onClick={runAll} disabled={loading}>Run All (bulk)</button>
        </div>
      </div>

      <div className="overflow-x-auto min-h-[120px]">
        {loading ? (
          <div className="p-2 text-sm text-gray-500">Loading...</div>
        ) : rows.length === 0 ? (
          <div className="p-2 text-sm text-gray-500">
            No offers found. Check credentials or server/db/pricebot.json.
          </div>
        ) : (
          <table className="min-w-full text-sm">
            <thead className="text-left text-gray-500">
              <tr>
                <th className="p-2">Name</th>
                <th className="p-2">Variant ID</th>
                <th className="p-2">Our Price</th>
                <th className="p-2">Min</th>
                <th className="p-2">Max</th>
                <th className="p-2">Step</th>
                <th className="p-2">Interval</th>
                <th className="p-2">Opponents</th>
                <th className="p-2">Active</th>
                <th className="p-2">Run</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.sku} className="border-t border-gray-200/70 dark:border-gray-700/60">
                  <td className="p-2">
                    <div className="font-medium">{row.name}</div>
                    <div className="text-xs text-gray-500">{row.sku}</div>
                  </td>
                  <td className="p-2">{row.productId}</td>
                  <td className="p-2">{row.price?.toLocaleString('ru-RU')}</td>

                  <td className="p-2">
                    <input className="input w-24" type="number" value={row.settings.min}
                      onChange={e => saveSettings(row.sku, { min: Number(e.target.value) })} />
                  </td>
                  <td className="p-2">
                    <input className="input w-24" type="number" value={row.settings.max}
                      onChange={e => saveSettings(row.sku, { max: Number(e.target.value) })} />
                  </td>
                  <td className="p-2">
                    <input className="input w-20" type="number" min={1} value={row.settings.step}
                      onChange={e => saveSettings(row.sku, { step: Math.max(1, Number(e.target.value)) })} />
                  </td>
                  <td className="p-2">
                    <input className="input w-20" type="number" min={1} max={10} value={row.settings.interval}
                      onChange={e => saveSettings(row.sku, { interval: Math.min(10, Math.max(1, Number(e.target.value))) })} />
                  </td>
                  <td className="p-2">
                    <button className="btn-link" onClick={() => openOpponents(row.sku)}>
                      {row.opponents || 0}
                    </button>
                  </td>
                  <td className="p-2">
                    <input type="checkbox" checked={row.settings.active}
                      onChange={e => saveSettings(row.sku, { active: e.target.checked })} />
                  </td>
                  <td className="p-2">
                    <button className="btn-outline" onClick={() => reprice(row.sku, row.price)}>Run</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {modal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center" onClick={() => setModal(null)}>
          <div className="bg-white dark:bg-neutral-900 rounded-lg p-4 w-[560px]" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm text-gray-500">Opponents for</div>
              <div className="text-xs">{modal.sku}</div>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="text-left text-gray-500">
                  <tr><th className="p-2">Seller</th><th className="p-2">Price</th><th className="p-2">Bot?</th><th className="p-2">Ignore</th></tr>
                </thead>
                <tbody>
                  {modal.sellers.map(s => (
                    <tr key={s.name} className="border-t border-gray-200/70 dark:border-gray-700/60">
                      <td className="p-2">{s.name}</td>
                      <td className="p-2">{(s.price||0).toLocaleString('ru-RU')}</td>
                      <td className="p-2">{s.isBot ? 'Yes' : 'No'}</td>
                      <td className="p-2">
                        <button className="btn-outline" onClick={() => toggleIgnore(modal.sku, s.name, true)}>Ignore</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 text-right">
              <button className="btn-outline" onClick={() => setModal(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
----------------------------------

PHASE F — CLEANUP & VERIFY
10) Ensure a gitignored data folder exists:
- Create directory: apps/kaspi_offers_dashboard/server/db/
- Create empty file if needed: apps/kaspi_offers_dashboard/server/db/.gitkeep
- Add/ensure .gitignore ignores .env.local. (Do NOT ignore pricebot.json unless requested.)

11) Fix .env comment:
Open apps/kaspi_offers_dashboard/.env.local and change line `D# feature flags` to `# feature flags`.

12) Manual checks:
- GET http://localhost:3000/api/debug/merchant → expect { ok:true } with counts (if 401, refresh cookie).
- GET http://localhost:3000/api/merchant/offers → expect list of items with sku/productId/name/price.
- GET http://localhost:3000/pricebot → table is populated (no “No offers found”).
- Click an “Opponents” number → modal with sorted sellers.
- Run curl:
  curl -i -X POST http://localhost:3000/api/pricebot/reprice \
    -H "Content-Type: application/json" \
    -d '{"sku":"<some SKU>","price":8216,"cityId":"710000000"}'
  → expect { ok:true, result:[...] } and handle NOT_ENOUGH_HISTORY in UI.

•	“Stop condition” and “Out of scope”.
	•	“Ground rules” (no credentials in git, keep types strict, add tests for API handlers, etc.).
    
Stop only when EVERYTHING above is implemented and verified working end-to-end.