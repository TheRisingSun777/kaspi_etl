const BASE   = process.env.KASPI_MERCHANT_API_BASE!;
const MODE   = (process.env.KASPI_MERCHANT_AUTH_MODE || 'cookie') as 'cookie'|'token';
const COOKIE = process.env.KASPI_MERCHANT_COOKIE || '';
const MID    = process.env.KASPI_MERCHANT_ID!;
const DEFAULT_CITY = process.env.DEFAULT_CITY_ID || '710000000';

function headers(extra?: Record<string,string>) {
  const h: Record<string,string> = { 'Accept': 'application/json', 'User-Agent': 'KaspiOffersDashboard/1.0' };
  if (MODE === 'cookie') {
    if (!COOKIE) throw new Error('MISSING_COOKIE');
    h['Cookie'] = COOKIE;
    h['x-auth-version'] = '3';
    h['Referer'] = 'https://kaspi.kz/';
    h['Origin']  = 'https://kaspi.kz';
  }
  return { ...h, ...(extra || {}) };
}

async function api(path: string, init: RequestInit = {}) {
  const res = await fetch(`${BASE}${path}`, { ...init, headers: headers(init.headers as any), cache:'no-store' });
  const text = await res.text();
  if (!res.ok) throw new Error(`MerchantAPI ${res.status} ${res.statusText} :: ${text.slice(0,500)}`);
  try { return JSON.parse(text); } catch { return text; }
}

/** BFF LIST — already in your Network tab */
export async function listActiveOffers(page=0, limit=100) {
  const q = new URLSearchParams({
    m: MID, p: String(page), l: String(limit),
    a: 'true', t: '', c: '', lowStock: 'false', notSpecifiedStock: 'false'
  });
  const data = await api(`/bff/offer-view/list?${q.toString()}`);
  const items = Array.isArray((data as any).items) ? (data as any).items : [];
  return { items, total: Number((data as any).total ?? items.length) };
}

/** DETAILS by SKU (`s`) — you already captured this GET */
export async function getOfferDetailsBySku(sku: string) {
  const q = new URLSearchParams({ m: MID, s: sku });
  return api(`/bff/offer-view/details?${q.toString()}`);
}

/**
 * PRICE UPDATE — use the exact body shape you saw:
 * { merchantUid, sku, cityPrices:[{cityId, value}], availabilities:[...], model }
 *
 * Important: we fetch current details first and only swap the price, so we don't lose required fields.
 */

// … existing imports and helper functions …

/**
 * Update the price/discount for a single SKU by POSTing to the merchant API.
 * Based on the payload you saw in DevTools:
 * {
 *   merchantUID: "30141222",
 *   merchantSKU: "CL_OC_MEN_PRINT51_BLACK_112128130_50_(XL)",
 *   entries: [ { city: "710000000", price: 8699 } ]
 * }
 */
export async function updatePriceBySku({
  sku,
  newPrice,
  cityId = DEFAULT_CITY,
}: {
  sku: string;
  newPrice: number;
  cityId?: string;
}) {
  const body = {
    merchantUID: MID,
    merchantSKU: sku,
    entries: [
      {
        city: String(cityId),
        price: Number(newPrice),
      },
    ],
  };

  return api(`/price/trends/api/v1/mc/discount`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}