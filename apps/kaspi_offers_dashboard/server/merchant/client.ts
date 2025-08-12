import fs from 'node:fs'
import path from 'node:path'
const BASE   = process.env.KASPI_MERCHANT_API_BASE!;
const MODE   = (process.env.KASPI_MERCHANT_AUTH_MODE || 'cookie') as 'cookie'|'token';
const COOKIE = process.env.KASPI_MERCHANT_COOKIE || '';
const MID    = process.env.KASPI_MERCHANT_ID!;
const DEFAULT_CITY = process.env.DEFAULT_CITY_ID || '710000000';

// Lightweight debug logger configured at module import time
const LOG_DIR = path.join(process.cwd(), 'server');
const LOG_FILE = path.join(LOG_DIR, 'pricebot_debug.log');
try { if (!fs.existsSync(LOG_DIR)) fs.mkdirSync(LOG_DIR, { recursive: true }); } catch {}
const logger = {
  debug: (message: string, meta?: unknown) => {
    try {
      const line = `${new Date().toISOString()} ${message}${meta !== undefined ? ' ' + safeStringify(meta) : ''}`;
      fs.appendFileSync(LOG_FILE, line + '\n');
    } catch {}
  }
};
function safeStringify(v: unknown) { try { return JSON.stringify(v); } catch { return String(v); } }

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

  // Debug: payload we are about to send to Kaspi
  logger.debug('upload_prices:start', { endpoint: '/price/trends/api/v1/mc/discount', body });

  // Honor DRY_RUN env to skip actual HTTP POST but still log the payload
  const dryEnv = String(process.env.DRY_RUN || '').toLowerCase();
  const isDry = dryEnv === '1' || dryEnv === 'true' || dryEnv === 'yes';
  if (isDry) {
    logger.debug('upload_prices:dry_skip', { reason: 'DRY_RUN env active', body });
    // Emulate a lightweight OK response
    return { ok: true, dryRun: true, skipped: true, body } as unknown as any;
  }

  // Perform request directly to capture raw status + body for logging
  const res = await fetch(`${BASE}/price/trends/api/v1/mc/discount`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...headers() },
    body: JSON.stringify(body),
    cache: 'no-store',
  });
  const status = res.status;
  const text = await res.text();

  // Debug: raw HTTP response
  logger.debug('upload_prices:response', { status, body: text });

  // Preserve prior behavior: return parsed JSON when possible, else raw text; throw on HTTP error codes.
  if (!res.ok) {
    // surface HTTP error with body
    throw new Error(`MerchantAPI ${status} ${res.statusText} :: ${text.slice(0,500)}`);
  }
  try { return JSON.parse(text); } catch { return text; }
}