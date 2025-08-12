import { NextRequest, NextResponse } from 'next/server';
import fs from 'node:fs';
import path from 'node:path';

// Kaspi endpoint
const OFFERS_API = 'https://kaspi.kz/yml/offer-view/offers';

// Read merchant cookie from server/merchant/<merchantId>.cookie.json { "cookie": "..." }
function readKaspiCookie(merchantId?: string | null): string {
  try {
    if (!merchantId) return '';
    const p = path.join(process.cwd(), 'server', 'merchant', `${merchantId}.cookie.json`);
    const raw = fs.readFileSync(p, 'utf8');
    const j = JSON.parse(raw);
    return String(j.cookie || '');
  } catch {
    return '';
  }
}

// Small helper: JSON/text fetch with consistent headers + retries
async function tryJson(url: string, init: RequestInit, tries = 2): Promise<any | null> {
  let lastErr: any;
  for (let i = 0; i < tries; i++) {
    try {
      const resp = await fetch(url, init);
      const text = await resp.text(); // read once so we can log on errors
      if (!resp.ok) {
        // Surface Kaspi's HTML error page text (403 etc) in our logs
        console.error('[kaspi-fetch]', resp.status, url);
        console.info('[kaspi-body]', text.slice(0, 400));
        continue;
      }
      // Try JSON parse (endpoint sometimes returns an array at top-level)
      try { return JSON.parse(text); } catch { /* fall through */ }
      return null;
    } catch (e) {
      lastErr = e;
      await new Promise(r => setTimeout(r, 200 + 300 * i));
    }
  }
  if (lastErr) console.error('[kaspi-fetch:err]', lastErr);
  return null;
}

export async function GET(req: NextRequest) {
  const u = new URL(req.url);
  const productId = u.searchParams.get('productId') || '';
  const sku = u.searchParams.get('sku') || '';
  const cityId = u.searchParams.get('cityId') || '710000000';
  const merchantId = u.searchParams.get('merchantId') || '';

  if (!productId && !sku) {
    return NextResponse.json({ ok: false, error: 'Missing productId or sku' }, { status: 400 });
  }

  // Headers that mirror browser requests; include cookie & X-KS-City
  const cookieStr = readKaspiCookie(merchantId) ||
    `locale=ru-RU; kaspi.storefront.cookie.city=${cityId}`;

  const referer = productId
    ? `https://kaspi.kz/shop/p/-${productId}/?c=${cityId}`
    : `https://kaspi.kz/`;

  const baseHeaders: Record<string, string> = {
    'Accept': 'application/json, text/*',
    'Accept-Language': 'ru-KZ,ru;q=0.9,en;q=0.8',
    'Content-Type': 'application/json; charset=UTF-8',
    'Origin': 'https://kaspi.kz',
    'Referer': referer,
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'X-KS-City': cityId,
    'Cookie': cookieStr,
  };

  // 1) POST JSON (preferred by the site lately)
  const asJsonBody = JSON.stringify({ productId, cityId });
  let js = await tryJson(OFFERS_API, { method: 'POST', headers: baseHeaders, body: asJsonBody }, 2);

  // 2) If null (blocked), try GET with qs (old shape still works sometimes)
  if (!js) {
    const qs = `?productId=${encodeURIComponent(productId)}&cityId=${encodeURIComponent(cityId)}&page=0&sort=DEFAULT&limit=100`;
    js = await tryJson(OFFERS_API + qs, { method: 'GET', headers: { ...baseHeaders, 'Content-Type': '' } }, 1);
  }

  // 3) If still null, try POST form
  if (!js) {
    const formBody = `productId=${encodeURIComponent(productId)}&cityId=${encodeURIComponent(cityId)}`;
    js = await tryJson(OFFERS_API, {
      method: 'POST',
      headers: { ...baseHeaders, 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formBody,
    }, 1);
  }

  if (!js) {
    return NextResponse.json({ ok: false, error: 'Kaspi returned no JSON (blocked?)' }, { status: 502 });
  }

  // Normalize shape: endpoint can be either top-level array or {items:[]}
  const offers: any[] = Array.isArray(js) ? js : (Array.isArray(js?.items) ? js.items : []);

  // Map to the modal's expected fields
  const sellers = offers.map((o: any) => ({
    merchantId: String(o.merchantId ?? o.merchantUID ?? ''),
    merchantName: o.merchantName ?? o.name ?? '',
    price: Number(o.price ?? 0),
    isYou: merchantId && String(o.merchantId) === String(merchantId),
  })).filter(s => s.merchantId);

  return NextResponse.json({ ok: true, items: sellers });
}