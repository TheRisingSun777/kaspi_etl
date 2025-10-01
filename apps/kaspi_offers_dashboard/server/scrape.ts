// server/scrape.ts
import { chromium, type BrowserContext, type Locator, type Page } from 'playwright';
import fs from 'node:fs/promises';
import { getCached as getMasterCached, setCached as setMasterCached } from './cache';

import type { AnalyzeResult, Variant, Seller } from '@/lib/types';

const DEFAULT_TIMEOUT = 25_000;
const CITY_NAMES: Record<string, string[]> = {
  '710000000': ['Астана', 'Нур-Султан', 'Astana'],
  '750000000': ['Алматы', 'Almaty'],
  '620000000': ['Шымкент', 'Shymkent'],
};

const DEBUG = process.env.DEBUG_SCRAPE === '1';

export type FlatSellerRow = {
  product_url: string;
  product_code: string;
  seller_name: string;
  price_kzt: number;
};

function ensureCityParam(url: string, cityId: string): string {
  try {
    const parsed = new URL(url);
    parsed.searchParams.set('c', cityId);
    return parsed.toString();
  } catch {
    const normalized = url.startsWith('http') ? url : `https://kaspi.kz${url.startsWith('/') ? '' : '/'}${url}`;
    return ensureCityParam(normalized, cityId);
  }
}

function productCodeFromUrl(url: string): string | null {
  const match = url.match(/-(\d+)(?:[/?#]|$)/);
  if (match) return match[1];
  const fallback = url.match(/\/p\/(\d+)(?:[/?#]|$)/);
  return fallback ? fallback[1] : null;
}

function sanitizeSellerName(raw: string): string {
  return raw
    .replace(/[",'`’‘“”]/g, ' ')
    .replace(/\u00a0/g, ' ')
    .replace(/[\r\n\t]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function sanitizePrice(value: unknown): number {
  const str = String(value ?? '').replace(/[^\d]/g, '');
  if (!str) return NaN;
  const num = Number(str);
  return Number.isFinite(num) ? Math.round(num) : NaN;
}

function randomBetween(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

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
    // Some deployments use city_id as well
    { name: 'city_id', value: cityId, domain: 'kaspi.kz', path: '/', httpOnly: false, secure: true },
    { name: 'city_id', value: cityId, domain: '.kaspi.kz', path: '/', httpOnly: false, secure: true },
  ]);
}

function blockHeavyButKeepCss(route: any) {
  const t = route.request().resourceType();
  if (t === 'image' || t === 'media' || t === 'font') return route.abort();
  return route.continue();
}

async function findNextPaginationControl(page: Page): Promise<Locator | null> {
  const selectors = [
    'button[aria-label*="следующ" i]',
    'a[aria-label*="следующ" i]',
    'button:has-text("Следующая")',
    'a:has-text("Следующая")',
    '.pagination__item_next button',
    '.pagination__item_next a',
    '.pagination__link_next',
  ];

  for (const selector of selectors) {
    const candidate = page.locator(selector).first();
    if ((await candidate.count()) === 0) continue;
    const isDisabled = await candidate
      .evaluate((el) => {
        const elem = el as HTMLElement;
        const ariaDisabled = elem.getAttribute('aria-disabled');
        return (
          elem.classList.contains('disabled') ||
          elem.hasAttribute('disabled') ||
          ariaDisabled === 'true'
        );
      })
      .catch(() => false);
    if (isDisabled) continue;
    return candidate;
  }
  return null;
}

async function captureSellerSectionSignature(page: Page): Promise<string> {
  return page
    .evaluate(() => {
      const candidates = [
        document.querySelector('[data-cy*="seller"]'),
        document.querySelector('.sellers-table'),
        document.querySelector('.merchant-list'),
        document.querySelector('.sellers-list'),
        document.querySelector('.sellers-table__body'),
      ];
      const node = candidates.find(Boolean) as HTMLElement | undefined;
      return node ? node.innerHTML : '';
    })
    .catch(() => '');
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
  // Wait for configurator object if present
  await page
    .waitForFunction(
      'typeof window !== "undefined" && !!(window as any).BACKEND && !!(window as any).BACKEND.components && !!(window as any).BACKEND.components.configurator',
      { timeout: 7000 }
    )
    .catch(() => {});

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
  await page
    .waitForFunction(
      'typeof window !== "undefined" && !!(window as any).BACKEND && !!(window as any).BACKEND.components && !!(window as any).BACKEND.components.configurator',
      { timeout: 7000 }
    )
    .catch(() => {});

  const details = await extractPageDetails(page);

  return { page, captured, details };
}

export async function scrapeSellersFlat(
  page: Page,
  productUrl: string,
  cityId: number
): Promise<{ rows: FlatSellerRow[]; total: number; product_code: string; pages: Array<{ page: number; got: number }>; dupFiltered: number }> {
  const city = String(cityId);
  page.setDefaultNavigationTimeout(60_000);
  page.setDefaultTimeout(45_000);
  await setCityCookie(page.context(), city);

  const targetUrl = ensureCityParam(productUrl, city);
  const urlDerivedCode = productCodeFromUrl(targetUrl) || '';

  await page.route('**/*', blockHeavyButKeepCss);

  let navError: unknown;
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: DEFAULT_TIMEOUT });
      navError = null;
      break;
    } catch (err) {
      navError = err;
      if (attempt === 1) throw err;
      await sleep(400 + Math.random() * 500);
    }
  }
  if (navError) throw navError;

  await ensureCity(page, city);
  await page.waitForLoadState('domcontentloaded', { timeout: DEFAULT_TIMEOUT }).catch(() => {});
  await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});

  const tabSelectors = [
    '[role="tab"]:has-text("Предложения продавцов")',
    '[role="tab"]:has-text("Продавцы")',
    'a:has-text("Предложения продавцов")',
    'a:has-text("Продавцы")',
    'button:has-text("Предложения продавцов")',
    'button:has-text("Продавцы")',
  ];
  for (const selector of tabSelectors) {
    const tab = page.locator(selector).first();
    if ((await tab.count()) === 0) continue;
    await tab.click({ timeout: 4_000 }).catch(() => {});
    await page.waitForLoadState('domcontentloaded', { timeout: 15_000 }).catch(() => {});
    await page
      .waitForSelector('.sellers-table, .sellers, .sellers-table__body, .merchant-list', { timeout: 15_000 })
      .catch(() => {});
    break;
  }

  const listSel = '.sellers-table__body, .sellers, .merchant-list';
  const pageNumSel = '.pagination a, .pagination__link, .pager a';
  const nextSel = 'a:has-text("Следующая"), button:has-text("Следующая")';

  await page.waitForSelector(listSel, { timeout: 15_000 }).catch(() => {});

  const listSignature = async () =>
    (await page.$eval(listSel, (el) => el.textContent || '').catch(() => ''))
      .replace(/\s+/g, ' ')
      .trim();

  let maxPage = 1;
  try {
    const nums = await page
      .$$eval(
        pageNumSel,
        (els) =>
          els
            .map((el) => parseInt((el.textContent || '').trim(), 10))
            .filter((n) => !Number.isNaN(n))
      )
      .catch(() => [] as number[]);
    if (nums.length) maxPage = Math.max(1, ...nums);
  } catch {}
  const allRows: FlatSellerRow[] = [];
  const seen = new Set<string>();
  const pagesMeta: Array<{ page: number; got: number }> = [];
  let duplicatesFiltered = 0;

  const productCodeFromPage =
    (await page
      .evaluate(() => {
        const meta = document.querySelector(
          'meta[name="product_id"], meta[property="product:id"], meta[name="product:id"]'
        ) as HTMLMetaElement | null;
        if (meta?.content) return meta.content;
        const dataset = document.querySelector('[data-product-id], [data-productid]') as HTMLElement | null;
        if (dataset) {
          const direct =
            dataset.getAttribute('data-product-id') ||
            dataset.getAttribute('data-productid') ||
            (dataset as any).dataset?.productId ||
            '';
          if (direct) return direct;
        }
        const text = document.body ? document.body.innerText || '' : '';
        const match = text.match(/Код товара[^\d]*(\d{5,})/i);
        return match ? match[1] : null;
      })
      .catch(() => null)) || '';

  const productCode = productCodeFromPage || urlDerivedCode;

  const useNextFallback = maxPage === 1;

  for (let pageIndex = 1; ; pageIndex++) {
    if (pageIndex > 1) {
      const before = await listSignature();
      let clicked = false;
      if (!useNextFallback) {
        const pageLink = page.locator(`${pageNumSel}:has-text("${pageIndex}")`).first();
        if ((await pageLink.count()) > 0) {
          await pageLink.click({ timeout: 3_000 }).catch(() => {});
          clicked = true;
        }
      }
      if (!clicked) {
        const nextLink = page.locator(nextSel).first();
        if ((await nextLink.count()) > 0) {
          await nextLink.click({ timeout: 3_000 }).catch(() => {});
          clicked = true;
        }
      }

      if (!clicked) {
        break;
      }

      await Promise.race([
        page.waitForFunction(
          (sel, prev) => {
            const el = document.querySelector(sel);
            if (!el) return false;
            const now = (el.textContent || '').replace(/\s+/g, ' ').trim();
            return now && now !== prev;
          },
          { timeout: 12_000 },
          listSel,
          before
        ),
        page.waitForTimeout(12_000),
      ]);
      await page.waitForLoadState('networkidle', { timeout: 5_000 }).catch(() => {});
    }

    const sellers = await parseSellersFromDom(page).catch(() => []);
    const pageRows: FlatSellerRow[] = [];
    for (const seller of sellers) {
      const cleanName = sanitizeSellerName(seller.name || '');
      const cleanPrice = sanitizePrice(seller.price);
      if (!cleanName || !Number.isFinite(cleanPrice) || cleanPrice <= 0) continue;
      const key = `${cleanName.toLowerCase()}||${cleanPrice}`;
      if (seen.has(key)) {
        duplicatesFiltered += 1;
        continue;
      }
      seen.add(key);
      const row: FlatSellerRow = {
        product_url: targetUrl,
        product_code: productCode,
        seller_name: cleanName,
        price_kzt: cleanPrice,
      };
      allRows.push(row);
      pageRows.push(row);
    }
    pagesMeta.push({ page: pageIndex, got: pageRows.length });

    if (!useNextFallback) {
      if (pageIndex >= maxPage) break;
    } else {
      const nextLink = page.locator(nextSel).first();
      const hasNext = (await nextLink.count()) > 0;
      if (!hasNext) break;
      const ariaDisabled = await nextLink.getAttribute('aria-disabled').catch(() => null);
      const classAttr = await nextLink.getAttribute('class').catch(() => null);
      if (ariaDisabled === 'true' || (classAttr || '').toLowerCase().includes('disabled')) break;
    }
  }

  await page.unroute('**/*', blockHeavyButKeepCss).catch(() => {});

  return {
    rows: allRows,
    total: allRows.length,
    product_code: productCode,
    pages: pagesMeta,
    dupFiltered: duplicatesFiltered,
  };
}

async function parseSellersFromDom(page: Page): Promise<Seller[]> {
  const selectors = [
    '[data-cy*="sellers"] li',
    '.sellers-list li',
    '.merchant-list li',
    '.merchant__root, .merchant-list__item, .sellers-list__item',
    '.sellers-table__row',
    '.sellers-table tr',
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
            (root.querySelector('.sellers-table__merchant-name') as HTMLElement)?.textContent?.trim() ||
            (root.querySelector('[data-merchant-name]') as HTMLElement)?.textContent?.trim() ||
            (root.querySelector('a[href*="/shop/seller"]') as HTMLElement)?.textContent?.trim() ||
            (root.querySelector('[class*="merchant"][class*="name"]') as HTMLElement)?.textContent?.trim() ||
            (text.split('\n')[0] || '').trim();

          const priceTxt =
            (root.querySelector('.sellers-table__price-cell-text') as HTMLElement)?.textContent ||
            (root.querySelector('[data-merchant-price]') as HTMLElement)?.textContent ||
            (root.querySelector('[class*="price"]') as HTMLElement)?.textContent ||
            text;

          const num = (priceTxt.match(/[\d\s]+/g)?.join('') || '').replace(/\s/g, '');
          const price = Number(num);

          const delA = (root.querySelector('.sellers-table__delivery, .sellers-table__delivery-text') as HTMLElement)?.textContent?.trim() || ''
          const delB = (root.querySelector('.sellers-table__delivery-price') as HTMLElement)?.textContent?.trim() || ''
          const postamatLine = (root.querySelector('[data-test*="postomat" i]') as HTMLElement)?.textContent?.trim() || (text.match(/Постомат[^\n]+/i)?.[0] || '').trim() || ''
          const deliveryLine = delA || (root.querySelector('[data-test*="delivery"]') as HTMLElement)?.textContent?.trim() || (root.querySelector('[class*="delivery"]') as HTMLElement)?.textContent?.trim() || (text.match(/Доставка[^\n]+/i)?.[0] || '').trim()
          const delivery = [postamatLine, deliveryLine, delB].filter(Boolean).join(' | ')

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

        const postamatLine = (text.match(/Postomat[^\n]+/i)?.[0] || '').trim();
        const deliveryLine = (text.match(/Доставка[^\n]+/i)?.[0] || '').trim();
        const delivery = [postamatLine, deliveryLine].filter(Boolean).join(' | ');

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

async function discoverVariantMap(page: Page): Promise<Record<string, string>> {
  try {
    const data = await page.evaluate(() => {
      const out: Record<string, string> = {};

      const html = document.documentElement.innerHTML || '';

      // 0) Directly read global BACKEND object if available
      try {
        // @ts-ignore
        const conf = (window as any)?.BACKEND?.components?.configurator;
        if (conf && Array.isArray(conf.matrix)) {
          function walk(node: any, ctx: { dim?: string }) {
            const ch = node?.characteristic || {};
            const title = String(ch.title || ch.id || '').toLowerCase();
            const next: { dim?: string } = { ...ctx };
            if (/размер|size/.test(title)) {
              const sizeId = String(ch.id || '').trim();
              const dim = String((ch.values?.[0]?.dimension || ch.dimension || '')).trim();
              if (node.productCode && sizeId) {
                const pid = String(node.productCode);
                const label = `${sizeId}${dim ? ` ${dim}` : ''}`;
                out[pid] = label;
              }
              if (dim) next.dim = dim;
            }
            if (Array.isArray(node?.matrix)) for (const c of node.matrix) walk(c, next);
          }
          for (const n of conf.matrix) walk(n, {});
        }
      } catch {}

      // 1) Preferred: BACKEND.components.configurator matrix
      try {
        const m = html.match(/BACKEND\.components\.configurator\s*=\s*(\{[\s\S]*?\});/);
        if (m) {
          const conf = JSON.parse(m[1] as string);

          function walk(node: any, ctx: { color?: string; size?: string; dim?: string }) {
            if (!node) return;
            const next = { ...ctx } as { color?: string; size?: string; dim?: string };
            const ch = node.characteristic || {};
            const title = String(ch.title || ch.id || '').toLowerCase();
            if (/цвет|colour|color/.test(title)) {
              next.color = String(ch.id || ch.value || '').trim();
            }
            if (/размер|size/.test(title)) {
              const sizeId = String(ch.id || '').trim();
              const dim = String((ch.values?.[0]?.dimension || ch.dimension || '')).trim();
              next.size = sizeId;
              next.dim = dim || next.dim;
            }
            if (node.productCode) {
              const pid = String(node.productCode);
              const dim = next.dim ? ` ${next.dim}` : '';
               const label = `${next.size || ''}${dim}`.trim();
               if (pid && label) out[pid] = label;
               // Attach color/size/name metadata when available for export
               // @ts-ignore
               if (!out[pid] && next.color) out[pid] = label || String(next.color);
            }
            if (Array.isArray(node.matrix)) {
              for (const child of node.matrix) walk(child, next);
            }
          }
          if (Array.isArray(conf?.matrix)) for (const n of conf.matrix) walk(n, {});
        }
      } catch {}

      // 2) Fallback: __KASPI__ variants
      try {
        const m2 = html.match(/__KASPI__\s*=\s*(\{[\s\S]*?\});/);
        if (m2) {
          const root = JSON.parse(m2[1] as string);
          const vlist = root?.pageData?.variants || root?.variants || [];
          for (const v of vlist) {
            const id = String(v?.id ?? v?.productId ?? '');
            const label = String(v?.label ?? v?.name ?? '').trim();
            if (id && label && !out[id]) out[id] = label;
          }
        }
      } catch {}

      // 3) Fallback: anchors that look like product links
      try {
        const sizeRegex = /(\d{2}\/(?:XS|S|M|L|XL|XXL)\s*RUS|\d{2}\s*\/(?:XS|S|M|L|XL|XXL)|(?:XS|S|M|L|XL|XXL)\s*RUS|\d{2}\/(?:XS|S|M|L|XL|XXL))/i;
        const anchors = Array.from(document.querySelectorAll('a[href*="/shop/p/"]')) as HTMLAnchorElement[];
        for (const a of anchors) {
          const href = a.href || '';
          const m = href.match(/-(\d+)\/?$/);
          const id = m ? m[1] : '';
          const label = (a.textContent || '').trim();
          if (id && label && (sizeRegex.test(label) || /(черн|бел|сер|красн|син|зел)/i.test(label))) {
            if (!out[id]) out[id] = label;
          }
        }
      } catch {}

      return out;
    });
    return data || {};
  } catch {
    return {};
  }
}

function discoverVariantMapFromHtml(html: string): Record<string, string> {
  const out: Record<string, string> = {}
  try {
    const marker = 'BACKEND.components.configurator'
    let idx = html.indexOf(marker)
    if (idx >= 0) {
      idx = html.indexOf('=', idx)
      if (idx > 0) {
        // Extract balanced JSON starting at first '{'
        let start = html.indexOf('{', idx)
        let depth = 0
        let end = -1
        for (let i = start; i < html.length; i++) {
          const ch = html[i]
          if (ch === '{') depth++
          else if (ch === '}') {
            depth--
            if (depth === 0) { end = i; break }
          }
        }
        if (start >= 0 && end > start) {
          const jsonStr = html.slice(start, end + 1)
          const conf = JSON.parse(jsonStr)
          function walk(node: any, ctx: { dim?: string }) {
            const ch = node?.characteristic || {}
            const title = String(ch.title || ch.id || '').toLowerCase()
            const next: { dim?: string } = { ...ctx }
            if (/размер|size/.test(title)) {
              const sizeId = String(ch.id || '').trim()
              const dim = String((ch.values?.[0]?.dimension || ch.dimension || '')).trim()
              if (node.productCode && sizeId) {
                const pid = String(node.productCode)
                const label = `${sizeId}${dim ? ` ${dim}` : ''}`
                out[pid] = label
              }
              if (dim) next.dim = dim
            }
            if (Array.isArray(node?.matrix)) for (const c of node.matrix) walk(c, next)
          }
          if (Array.isArray(conf?.matrix)) for (const n of conf.matrix) walk(n, {})
        }
      }
    }
  } catch {}
  return out
}

function normalizeRuDateToDotted(dateLike: string, twoDigitYear = false): string {
  if (!dateLike) return '';
  const months: Record<string, number> = {
    'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
    'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
  };
  const m = dateLike.toLowerCase().match(/(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)/);
  if (!m) return '';
  const d = parseInt(m[1], 10);
  const mo = months[m[2]];
  const year = new Date().getFullYear();
  const yy = String(year).slice(-2);
  return twoDigitYear ? `${d}.${mo}.${yy}` : `${d}.${mo}.${year}`;
}

function normalizeDelivery(text: string): string {
  if (!text) return '';
  const t = text.replace(/\s+/g, ' ').trim();
  const lines = text.split(/\n|\r|\.|;|\u2028|\u2029/).map((s) => s.trim()).filter(Boolean);
  let postamat = '', delivery = '';
  for (const ln of lines) {
    if (!postamat && /postomat|постомат/i.test(ln)) postamat = ln;
    if (!delivery && /доставка/i.test(ln)) delivery = ln;
  }
  if (!postamat && /postomat|постомат/i.test(t)) postamat = t;
  if (!delivery && /доставка/i.test(t)) delivery = t;

  const pDate = normalizeRuDateToDotted(postamat, false);
  const dDate = normalizeRuDateToDotted(delivery, true);
  if (pDate || dDate) {
    return `${pDate ? `postamat - ${pDate}` : ''}${pDate && dDate ? ', ' : ''}${dDate ? `delivery - ${dDate}` : ''}`.trim();
  }
  return t;
}

async function extractPageDetails(page: Page): Promise<{ sizesAll?: string[]; colorsAll?: string[]; ratingCount?: number; imageUrl?: string }> {
  try {
    const details = await page.evaluate(() => {
      const out: { sizesAll?: string[]; colorsAll?: string[]; ratingCount?: number; imageUrl?: string } = {};

      // rating count near reviews link (e.g., "(85 отзывов)")
      try {
        const anchor = Array.from(document.querySelectorAll('a')).find((el) => /отзыв/i.test(el.textContent || ''));
        if (anchor) {
          const m = (anchor.textContent || '').match(/(\d+)/);
          if (m) out.ratingCount = Number(m[1]);
        }
      } catch {}

      // product main image
      try {
        const og = document.querySelector('meta[property="og:image"]') as HTMLMetaElement | null;
        const ogUrl = og?.getAttribute('content') || '';
        if (ogUrl) out.imageUrl = ogUrl;
      } catch {}
      if (!out.imageUrl) {
        const img = document.querySelector('img[src*="/pictures/"]') as HTMLImageElement | null;
        if (img?.src) out.imageUrl = img.src;
      }

      function uniq(values: string[]): string[] {
        const set = new Set<string>();
        for (const v of values) {
          const t = v.trim();
          if (t) set.add(t);
        }
        return Array.from(set);
      }

      // try to use embedded configurator JSON first
      try {
        const html = document.documentElement.innerHTML || '';
        const m = html.match(/BACKEND\.components\.configurator\s*=\s*(\{[\s\S]*?\});/);
        if (m) {
          const conf = JSON.parse(m[1] as string);
          const sizes: string[] = [];
          const colors: string[] = [];
          function walk(node: any) {
            const ch = node?.characteristic || {};
            const title = String(ch.title || ch.id || '').toLowerCase();
            if (/цвет|colour|color/.test(title)) {
              const val = String(ch.id || ch.value || '').trim();
              if (val) colors.push(val.charAt(0).toUpperCase() + val.slice(1));
            }
            if (/размер|size/.test(title)) {
              const sizeId = String(ch.id || '').trim();
              const dim = String((ch.values?.[0]?.dimension || ch.dimension || '')).trim();
              if (sizeId) sizes.push(`${sizeId}${dim ? ` ${dim}` : ''}`);
            }
            if (Array.isArray(node?.matrix)) for (const c of node.matrix) walk(c);
          }
          if (Array.isArray(conf?.matrix)) for (const n of conf.matrix) walk(n);
          if (sizes.length) out.sizesAll = Array.from(new Set(sizes));
          if (colors.length) out.colorsAll = Array.from(new Set(colors));
        }
      } catch {}

      // then __KASPI__ variants
      try {
        const html = document.documentElement.innerHTML || '';
        const match = html.match(/__KASPI__\s*=\s*(\{[\s\S]*?\});/);
        if (match) {
          const root = JSON.parse(match[1]);
          const vlist = root?.pageData?.variants || root?.variants || [];
          const labels: string[] = [];
          for (const v of vlist) if (v?.label) labels.push(String(v.label));
          if (labels.length) {
            // crude size extraction
            const sizes: string[] = [];
            const colors: string[] = [];
            for (const L of labels) {
              const sm = L.match(/(\d{2}\/(?:XS|S|M|L|XL|XXL)\s*RUS|\d{2}\s*\/(?:XS|S|M|L|XL|XXL)|XS|S|M|L|XL|XXL|\d{2,3}[\/]?\w*)/i);
              if (sm) sizes.push(sm[1]);
              const cm = L.match(/(черный|белый|серый|серебристый|синий|красный|зеленый|фиолетовый|желтый|оранжевый|коричневый)/i);
              if (cm) colors.push(cm[1]);
            }
            if (sizes.length) out.sizesAll = uniq(sizes);
            if (colors.length) out.colorsAll = uniq(colors.map((s) => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase()));
          }
        }
      } catch {}

      // fallback from full page text for sizes/colors
      if (!out.sizesAll) {
        const text = (document.body.innerText || '');
        const sizeCandidates = Array.from(text.matchAll(/\b(\d{2}\/(?:XS|S|M|L|XL|XXL)\s*RUS|\d{2}\s*\/(?:XS|S|M|L|XL|XXL)|XS|S|M|L|XL|XXL|\d{2,3}[\/]?\w*)\b/gi)).map(m => m[1]);
        if (sizeCandidates.length) out.sizesAll = uniq(sizeCandidates);
      }
      if (!out.colorsAll) {
        const colorLabels = ['черный','белый','серый','серебристый','синий','красный','зеленый','фиолетовый','желтый','оранжевый','коричневый'];
        const text = (document.body.innerText || '').toLowerCase();
        const found: string[] = [];
        for (const c of colorLabels) if (text.includes(c)) found.push(c);
        if (found.length) out.colorsAll = uniq(found.map(s => s.charAt(0).toUpperCase() + s.slice(1)));
      }

      return out;
    });
    return details;
  } catch {
    return {};
  }
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
  // Master-level LRU cache
  const cacheKey = `${masterProductId}:${cityId}`
  const cachedMaster = getMasterCached<AnalyzeResult>(cacheKey)
  if (cachedMaster) return cachedMaster
  const headless = process.env.PW_HEADLESS !== '0';
  const slowMo = Number(process.env.PW_SLOWMO || '0');

  const browser = await chromium.launch({ headless, slowMo });
  const context = await browser.newContext({
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    locale: 'ru-KZ',
    timezoneId: 'Asia/Almaty',
  });
  await setCityCookie(context, cityId);

  const page = await context.newPage();
  await page.route('**/*', blockHeavyButKeepCss);

  const entryUrl = `https://kaspi.kz/shop/p/-${masterProductId}/?c=${cityId}`;
  await page.goto(entryUrl, { waitUntil: 'domcontentloaded', timeout: DEFAULT_TIMEOUT });
  await ensureCity(page, cityId);

  const productName =
    (await page.locator('h1').first().textContent().catch(() => ''))?.trim() || '';

  const entryDetails = await extractPageDetails(page);
  const entryHtml = await page.content();
  let variantMap = discoverVariantMapFromHtml(entryHtml);
  if (Object.keys(variantMap).length === 0) {
    // fallback to in-page discovery
    variantMap = await discoverVariantMap(page);
  }

  // Discover variants via embedded JSON first (ids + labels), fallback to link scan
  const hrefs: string[] = await page
    .locator('a[href*="/shop/p/"]')
    .evaluateAll((els) => els.map((a: any) => (a as HTMLAnchorElement).href));

  const ids = new Set<string>(Object.keys(variantMap));
  for (const h of hrefs) {
    const id = idFromHref(h);
    if (id) ids.add(id);
  }
  ids.add(masterProductId); // make sure the searched id is included
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
        const { page: vPage, captured, details } = await openVariantPage(context, id, cityId);

        let capturedJSON = 0;
        let parsedFromJSON = 0;
        let parsedFromDOM = 0;

        const fromCaptured = parseSellersFromCaptured(captured);
        capturedJSON = captured.length;
        parsedFromJSON = fromCaptured.length;

        let sellers = dedupeSellers(fromCaptured.map((s) => ({ ...s, deliveryDate: normalizeDelivery(s.deliveryDate || '') })));
        if (sellers.length === 0) {
          const dom = await parseSellersFromDom(vPage);
          parsedFromDOM = dom.length;
          sellers = dedupeSellers(dom.map((s) => ({ ...s, deliveryDate: normalizeDelivery(s.deliveryDate || '') })));
        }

        // Extract variant meta: color/size/rating and title
        const meta = await vPage.evaluate(() => {
          const result: { color?: string; size?: string; rating?: { avg?: number; count?: number } } = {}
          try {
            const rows = Array.from(document.querySelectorAll('tr, li, div'))
            for (const r of rows.slice(0, 500)) {
              const t = (r as HTMLElement).innerText || ''
              if (!result.color && /(^|\s)Цвет(\s|:)/i.test(t)) {
                const m = t.match(/Цвет\s*[:\-]?\s*([A-Za-zА-Яа-яёЁ\- ]{3,})/)
                if (m) result.color = m[1].trim().toLowerCase()
              }
              if (!result.size && /(^|\s)Размер(\s|:)/i.test(t)) {
                const m = t.match(/Размер\s*[:\-]?\s*([0-9XLMS\/ ]+\w*)/i)
                if (m) result.size = m[1].trim()
              }
            }
          } catch {}
          try {
            const scripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'))
            for (const s of scripts) {
              let json: any
              try { json = JSON.parse(s.textContent || '{}') } catch { continue }
              let agg = json && json.aggregateRating
              if (!agg && Array.isArray(json?.['@graph'])) {
                const node = json['@graph'].find((x:any)=> x && x.aggregateRating)
                agg = node?.aggregateRating
              }
              if (agg) {
                const avg = Number(agg.ratingValue)
                const count = Number(agg.reviewCount)
                if (!Number.isNaN(avg) || !Number.isNaN(count)) {
                  result.rating = { avg: Number.isNaN(avg) ? undefined : avg, count: Number.isNaN(count) ? undefined : count }
                  break
                }
              }
            }
          } catch {}
          if (!result.rating) {
            try {
              const rv = document.querySelector('[itemprop="ratingValue"], meta[itemprop="ratingValue"]') as any
              const rc = document.querySelector('[itemprop="reviewCount"], meta[itemprop="reviewCount"]') as any
              const avg = rv ? Number(rv.content || rv.getAttribute('content') || rv.textContent || '') : NaN
              const count = rc ? Number(rc.content || rc.getAttribute('content') || rc.textContent || '') : NaN
              if (!Number.isNaN(avg) || !Number.isNaN(count)) {
                result.rating = { avg: Number.isNaN(avg)? undefined: avg, count: Number.isNaN(count)? undefined: count }
              }
            } catch {}
          }
          if (!result.rating) {
            try {
              const link = Array.from(document.querySelectorAll('a, span')).find(el => /отзыв/i.test(el.textContent||''))
              if (link) {
                const m = (link.textContent||'').match(/(\d{1,4})/)
                if (m) result.rating = { avg: undefined, count: Number(m[1]) }
              }
            } catch {}
          }
          return result
        })

        const label = variantMap[id] || (await vPage.locator('h1').first().textContent().catch(() => ''))?.trim() || `Variant ${id}`;
        const title = (await vPage.locator('h1').first().textContent().catch(() => ''))?.trim() || label

        // Compute stats and price-bot flag
        const prices = sellers.map(s => s.price).filter(n => Number.isFinite(n)) as number[]
        const sorted = [...prices].sort((a,b)=>a-b)
        const min = sorted.length ? sorted[0] : undefined
        const max = sorted.length ? sorted[sorted.length-1] : undefined
        const median = sorted.length ? (sorted.length%2? sorted[(sorted.length-1)/2] : (sorted[sorted.length/2-1]+sorted[sorted.length/2])/2) : undefined
        const mean = sorted.length ? sorted.reduce((a,b)=>a+b,0)/sorted.length : undefined
        const variance = (sorted.length && mean!==undefined) ? sorted.reduce((a,b)=>a+Math.pow(b-mean,2),0)/sorted.length : undefined
        const stddev = variance!==undefined ? Math.sqrt(variance) : undefined
        const spread = (min!==undefined && max!==undefined) ? max-min : undefined
        if (min!==undefined) {
          const medianDelta = median !== undefined ? median - min : 0
          sellers = sellers.map(s => {
            const delta = s.price - (min as number)
            const pct = (min as number) > 0 ? delta / (min as number) : 0
            // heuristic: bots tend to be within +0..+15 KZT of min OR within +0..0.25% of min
            const nearMin = delta >= 0 && delta <= 15
            const nearPct = pct >= 0 && pct <= 0.0025
            // also consider when median is tight around min
            const tightMarket = (medianDelta <= 30)
            const isPriceBot = (nearMin || nearPct) && tightMarket
            return { ...s, isPriceBot }
          })
        }

        // short-term prediction (very simple heuristic): if >=2 bots present, expect further undercutting
        let predictedMin24h: number | undefined = undefined
        let predictedMin7d: number | undefined = undefined
        if (min!==undefined) {
          const botCount = sellers.filter(s=>s.isPriceBot).length
          if (botCount >= 2) {
            // assume 10–30 KZT further drop in 24h, 20–60 KZT in 7d (bounded by not going below 0)
            predictedMin24h = Math.max(0, (min as number) - 20)
            predictedMin7d = Math.max(0, (min as number) - 40)
          } else {
            predictedMin24h = min
            predictedMin7d = min
          }
        }

        // stability score (0..100): lower stddev vs min = higher stability
        let stabilityScore: number | undefined = undefined
        if (min!==undefined && stddev!==undefined) {
          const ratio = min > 0 ? Math.min(1, stddev / min) : 1
          stabilityScore = Math.round((1 - ratio) * 100)
        }

        if (DEBUG) {
          try {
            await fs.mkdir('data_raw/debug', { recursive: true });
            await fs.mkdir('data_raw/kaspi_debug', { recursive: true });
            const html = await vPage.content();
            await fs.writeFile(`data_raw/debug/variant_${id}.html`, html, 'utf8');
            await fs.writeFile(`data_raw/kaspi_debug/variant_${id}.html`, html, 'utf8');
            console.log(`[kaspi][${id}] capturedJSON=${capturedJSON} parsedFromJSON=${parsedFromJSON} parsedFromDOM=${parsedFromDOM} sellers=${sellers.length}`);
            if (sellers.length === 0) {
              await vPage.screenshot({ path: `data_raw/debug/variant_${id}_no_sellers.png`, fullPage: true }).catch(()=>{})
              await vPage.screenshot({ path: `data_raw/kaspi_debug/variant_${id}_no_sellers.png`, fullPage: true }).catch(()=>{})
            }
          } catch {}
        }

        await vPage.close();

        // merge details
        if (details?.sizesAll?.length) entryDetails.sizesAll = Array.from(new Set([...(entryDetails.sizesAll || []), ...details.sizesAll]));
        if (details?.colorsAll?.length) entryDetails.colorsAll = Array.from(new Set([...(entryDetails.colorsAll || []), ...details.colorsAll]));
        if (!entryDetails.imageUrl && details?.imageUrl) entryDetails.imageUrl = details.imageUrl;

        setCached(cityId, id, sellers, label);
        variants.push({
          productId: id,
          label: title || label,
          variantColor: meta.color || (entryDetails.colorsAll?.[0]?.toLowerCase()),
          variantSize: meta.size || variantMap[id],
          rating: meta.rating,
          sellersCount: sellers.length,
          sellers,
          stats: { min, median, max, spread, stddev, stabilityScore, predictedMin24h, predictedMin7d }
        });

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

  const result: AnalyzeResult = {
    masterProductId,
    productName,
    cityId,
    variants,
    productImageUrl: entryDetails.imageUrl,
    attributes: { sizesAll: entryDetails.sizesAll, colorsAll: entryDetails.colorsAll },
    variantMap: Object.fromEntries(Object.entries(variantMap).map(([k,v])=>[k,{ size: v }])),
  }
  setMasterCached(cacheKey, result)
  return result
}
