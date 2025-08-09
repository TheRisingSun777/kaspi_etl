// server/scrape.ts
import { chromium, type BrowserContext, type Page } from 'playwright';
import fs from 'node:fs/promises';

export type Seller = { name: string; price: number; deliveryDate: string };
export type Variant = { productId: string; label: string; sellersCount: number; sellers: Seller[] };
export type AnalyzeResult = {
  masterProductId: string;
  productName: string;
  cityId: string;
  variants: Variant[];
  meta: { scrapedAt: string; source: 'kaspi.kz'; notes?: string };
};

const DEFAULT_TIMEOUT = 25_000;
const CITY_NAMES: Record<string, string[]> = {
  '710000000': ['Астана', 'Нур-Султан', 'Astana'],
  '750000000': ['Алматы', 'Almaty'],
};

const DEBUG = process.env.DEBUG_SCRAPE === '1';

// Simple 2-minute in-memory cache per (cityId, productId)
type VariantCacheEntry = { sellers: Seller[]; label?: string; expiresAt: number };
const VARIANT_CACHE_TTL_MS = 2 * 60 * 1000;
const variantCache = new Map<string, VariantCacheEntry>();
function cacheKey(cityId: string, productId: string) {
  return `${cityId}:${productId}`;
}
function getCached(cityId: string, productId: string): VariantCacheEntry | undefined {
  const k = cacheKey(cityId, productId);
  const entry = variantCache.get(k);
  if (!entry || entry.expiresAt <= Date.now()) return undefined;
  return entry;
}
function setCached(cityId: string, productId: string, sellers: Seller[], label?: string) {
  const k = cacheKey(cityId, productId);
  variantCache.set(k, { sellers, label, expiresAt: Date.now() + VARIANT_CACHE_TTL_MS });
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

function idFromHref(href: string): string | null {
  const m = href.match(/-(\d+)\/?$/);
  return m ? m[1] : null;
}

async function setCityCookie(context: BrowserContext, cityId: string) {
  // Set on both apex and subdomain just in case
  await context.addCookies([
    { name: 'kaspi_city_id', value: cityId, domain: 'kaspi.kz', path: '/', httpOnly: false, secure: true },
    { name: 'kaspi_city_id', value: cityId, domain: '.kaspi.kz', path: '/', httpOnly: false, secure: true },
  ]);
}

function blockHeavyButKeepCss(route: any) {
  const t = route.request().resourceType();
  if (t === 'image' || t === 'media' || t === 'font') return route.abort();
  return route.continue();
}

async function ensureCity(page: Page, cityId: string) {
  // Handle the “Выберите ваш город” interstitial if it appears.
  const dialog = page.getByText(/Выберите ваш город/i);
  if ((await dialog.count()) > 0) {
    // Prefer a link that has ?c=<cityId>
    const byHref = page.locator(`a[href*="c=${cityId}"]`).first();
    if ((await byHref.count()) > 0) {
      await Promise.all([page.waitForNavigation({ waitUntil: 'domcontentloaded' }), byHref.click()]);
      return;
    }
    // Fallback: click by visible city name
    for (const nm of CITY_NAMES[cityId] ?? []) {
      const link = page.getByRole('link', { name: new RegExp(`^${nm}\\b`, 'i') }).first();
      if ((await link.count()) > 0) {
        await Promise.all([page.waitForNavigation({ waitUntil: 'domcontentloaded' }), link.click()]);
        return;
      }
    }
  }
}

async function openVariantPage(context: BrowserContext, id: string, cityId: string) {
  const page = await context.newPage();
  await page.route('**/*', blockHeavyButKeepCss);

  // Capture JSON responses that look relevant
  const captured: Array<{ url: string; json: any }> = [];
  page.on('response', async (res) => {
    try {
      const ct = (res.headers()['content-type'] || '').toLowerCase();
      if (!ct.includes('json')) return;
      const url = res.url();
      if (/api|offer|seller|merchant|price|catalog|stock|availability|listing|product/i.test(url)) {
        const json = await res.json().catch(() => null);
        if (json) captured.push({ url, json });
      }
    } catch { /* ignore */ }
  });

  // Add the city param to the URL as well as cookie (first load sometimes ignores cookie)
  const url = `https://kaspi.kz/shop/p/-${id}/?c=${cityId}`;
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: DEFAULT_TIMEOUT });
  await ensureCity(page, cityId);

  // Click the “Продавцы” tab if present (usually default, but harmless anyway)
  const sellersTab = page.getByText(/продавцы/i, { exact: false }).first();
  if ((await sellersTab.count()) > 0) {
    await sellersTab.click().catch(() => {});
  }

  // Scroll to nudge lazy-loading and give XHRs time to fire
  for (let i = 0; i < 3; i++) {
    await page.mouse.wheel(0, 1800);
    await page.waitForTimeout(350);
  }
  await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});

  return { page, captured };
}

async function parseSellersFromDom(page: Page): Promise<Seller[]> {
  const selectors = [
    '[data-cy*="sellers"] li',
    '.sellers-list li',
    '.merchant-list li',
    '.merchant__root, .merchant-list__item, .sellers-list__item',
  ];

  for (const sel of selectors) {
    const nodes = page.locator(sel);
    if ((await nodes.count()) > 0) {
      const sellers = await nodes.evaluateAll((els: Element[]) => {
        const out: any[] = [];
        for (const el of els) {
          const root = el as HTMLElement;
          const text = (root.innerText || '').trim();

          const name =
            (root.querySelector('[data-merchant-name]') as HTMLElement)?.textContent?.trim() ||
            (root.querySelector('a[href*="/shop/seller"]') as HTMLElement)?.textContent?.trim() ||
            (root.querySelector('[class*="merchant"][class*="name"]') as HTMLElement)?.textContent?.trim() ||
            (text.split('\n')[0] || '').trim();

          const priceTxt =
            (root.querySelector('[data-merchant-price]') as HTMLElement)?.textContent ||
            (root.querySelector('[class*="price"]') as HTMLElement)?.textContent ||
            text;

          const num = (priceTxt.match(/[\d\s]+/g)?.join('') || '').replace(/\s/g, '');
          const price = Number(num);

          const delivery =
            (root.querySelector('[data-test*="delivery"]') as HTMLElement)?.textContent?.trim() ||
            (root.querySelector('[class*="delivery"]') as HTMLElement)?.textContent?.trim() ||
            (text.match(/Доставка[^\n]+/i)?.[0] || '').trim();

          if (name && Number.isFinite(price) && price > 0) {
            out.push({ name, price, deliveryDate: delivery });
          }
        }
        return out;
      });
      if (sellers.length) return sellers;
    }
  }

  // Heuristic fallback: blocks that contain a “Выбрать” button (seller rows)
  const rows = page.locator('button:has-text("Выбрать")');
  if ((await rows.count()) > 0) {
    const sellers = await rows.evaluateAll((btns: Element[]) => {
      const seen = new Set<string>();
      const out: any[] = [];
      for (const btn of btns) {
        const row = (btn as HTMLElement).closest('li,div,tr,article') as HTMLElement | null;
        if (!row) continue;
        const text = (row.innerText || '').trim();

        const name =
          (row.querySelector('a[href*="/shop/seller"]') as HTMLElement)?.textContent?.trim() ||
          (row.querySelector('[class*="merchant"][class*="name"]') as HTMLElement)?.textContent?.trim() ||
          (text.split('\n')[0] || '').trim();

        const priceMatch = text.replace(/\s+/g, ' ').match(/(\d[\d\s]{3,})/);
        const price = priceMatch ? Number((priceMatch[1] || '').replace(/\s/g, '')) : NaN;

        const delivery = (text.match(/Доставка[^\n]+/i)?.[0] || '').trim();

        if (name && Number.isFinite(price) && price > 0 && !seen.has(name)) {
          seen.add(name);
          out.push({ name, price, deliveryDate: delivery });
        }
      }
      return out;
    });
    if (sellers.length) return sellers;
  }

  return [];
}

function parseSellersFromCaptured(captured: Array<{ url: string; json: any }>): Seller[] {
  const out: Seller[] = [];
  for (const { json } of captured) {
    const arr =
      Array.isArray((json as any)?.data) ? (json as any).data :
      Array.isArray((json as any)?.offers) ? (json as any).offers :
      Array.isArray(json as any) ? (json as any) : null;

    if (!arr) continue;

    for (const r of arr as any[]) {
      const name = r.merchantName || r.sellerName || r.merchant?.name || r.storeName;
      const priceRaw = r.price || r.minPrice || r?.prices?.card || r.priceBase || r.priceMin;
      const delivery = r.deliveryDate || r.delivery?.text || r.deliveryOption?.name || r.deliveryMessage || '';
      if (name && priceRaw) {
        const price = Math.round(Number(String(priceRaw).replace(/[^\d.]/g, '')));
        out.push({ name: String(name), price, deliveryDate: String(delivery) });
      }
    }
  }
  return out;
}

function dedupeSellers(sellers: Seller[]): Seller[] {
  const map = new Map<string, Seller>();
  for (const s of sellers) {
    const key = s.name.trim().toLowerCase();
    const price = Math.round(Number(s.price) || 0);
    const deliveryDate = String(s.deliveryDate || '');
    if (!map.has(key)) {
      map.set(key, { name: s.name.trim(), price, deliveryDate });
    } else {
      const cur = map.get(key)!;
      // Keep the lowest price; prefer non-empty delivery
      const betterPrice = price > 0 && (cur.price === 0 || price < cur.price);
      const betterDelivery = !cur.deliveryDate && deliveryDate;
      if (betterPrice || betterDelivery) {
        map.set(key, { name: cur.name, price: betterPrice ? price : cur.price, deliveryDate: betterDelivery ? deliveryDate : cur.deliveryDate });
      }
    }
  }
  // Sort by price asc
  return Array.from(map.values()).sort((a, b) => a.price - b.price);
}

export async function scrapeAnalyze(masterProductId: string, cityId: string): Promise<AnalyzeResult> {
  const headless = process.env.PW_HEADLESS !== '0';
  const slowMo = Number(process.env.PW_SLOWMO || '0');

  const browser = await chromium.launch({ headless, slowMo });
  const context = await browser.newContext({
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    locale: 'ru-KZ',
  });
  await setCityCookie(context, cityId);

  const page = await context.newPage();
  await page.route('**/*', blockHeavyButKeepCss);

  const entryUrl = `https://kaspi.kz/shop/p/-${masterProductId}/?c=${cityId}`;
  await page.goto(entryUrl, { waitUntil: 'domcontentloaded', timeout: DEFAULT_TIMEOUT });
  await ensureCity(page, cityId);

  const productName =
    (await page.locator('h1').first().textContent().catch(() => ''))?.trim() || '';

  // discover variant productIds from links on the page
  const hrefs: string[] = await page
    .locator('a[href*="/shop/p/"]')
    .evaluateAll((els) => els.map((a: any) => (a as HTMLAnchorElement).href));

  const ids = new Set<string>();
  for (const h of hrefs) {
    const id = idFromHref(h);
    if (id) ids.add(id);
  }
  ids.add(masterProductId); // ensure the main one is included
  const variantIds = Array.from(ids).slice(0, 24);

  const variants: Variant[] = [];

  for (const id of variantIds) {
    // Cache check
    const cached = getCached(cityId, id);
    if (cached) {
      variants.push({ productId: id, label: cached.label || `Variant ${id}`, sellersCount: cached.sellers.length, sellers: cached.sellers });
      // Backoff between pages even when cached
      await sleep(250 + Math.floor(Math.random() * 250));
      continue;
    }

    // Retry open & parse up to 3 times with backoff
    let lastErr: any;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const { page: vPage, captured } = await openVariantPage(context, id, cityId);

        let sellers = dedupeSellers(parseSellersFromCaptured(captured));
        if (sellers.length === 0) {
          sellers = dedupeSellers(await parseSellersFromDom(vPage));
        }

        const label =
          (await vPage.locator('h1').first().textContent().catch(() => ''))?.trim() ||
          `Variant ${id}`;

        if (DEBUG) {
          try {
            await fs.mkdir('data_raw/kaspi_debug', { recursive: true });
            await fs.writeFile(`data_raw/kaspi_debug/variant_${id}.html`, await vPage.content(), 'utf8');
            console.log(`[kaspi][${id}] captured=${captured.length} sellers=${sellers.length}`);
          } catch {}
        }

        await vPage.close();

        setCached(cityId, id, sellers, label);
        variants.push({ productId: id, label, sellersCount: sellers.length, sellers });

        break; // success
      } catch (e: any) {
        lastErr = e;
        // backoff 400ms, 900ms
        await sleep(400 + attempt * 500);
      }
    }
    // After retries, if still not pushed, record empty variant
    if (!variants.find((v) => v.productId === id)) {
      setCached(cityId, id, [], `Variant ${id}`);
      variants.push({ productId: id, label: `Variant ${id}`, sellersCount: 0, sellers: [] });
    }

    // Small rate-limit between variant pages
    await sleep(400 + Math.floor(Math.random() * 400));
  }

  await browser.close();

  return {
    masterProductId,
    productName,
    cityId,
    variants,
    meta: { scrapedAt: new Date().toISOString(), source: 'kaspi.kz' },
  };
}