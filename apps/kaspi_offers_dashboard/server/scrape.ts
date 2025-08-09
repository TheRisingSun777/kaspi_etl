import { chromium, type Browser, type BrowserContext, type Page, type Request } from 'playwright'

export type Seller = {
  name: string
  price: number
  deliveryDate: string
}

export type Variant = {
  productId: string
  label: string
  sellersCount: number
  sellers: Seller[]
}

export type AnalyzeResult = {
  masterProductId: string
  productName: string
  cityId: string
  variants: Variant[]
  meta: { scrapedAt: string; source: 'kaspi.kz'; notes?: string }
}

const SCRAPE_TIMEOUT_MS = 25_000
const MAX_RETRIES = 3
const VARIANT_CACHE_TTL_MS = 2 * 60 * 1000

type VariantCacheEntry = { sellers: Seller[]; label?: string; expiresAt: number }
const variantCache = new Map<string, VariantCacheEntry>()

function now() {
  return Date.now()
}

function isExpired(entry: VariantCacheEntry | undefined) {
  return !entry || entry.expiresAt <= now()
}

function rememberVariant(productId: string, sellers: Seller[], label?: string) {
  variantCache.set(productId, { sellers, label, expiresAt: now() + VARIANT_CACHE_TTL_MS })
}

function fromCached(productId: string): VariantCacheEntry | undefined {
  const entry = variantCache.get(productId)
  if (isExpired(entry)) return undefined
  return entry
}

async function withBrowser<T>(cityId: string, fn: (ctx: BrowserContext, browser: Browser) => Promise<T>): Promise<T> {
  const browser = await chromium.launch({ headless: true })
  try {
    const ctx = await browser.newContext({
      userAgent: 'Mozilla/5.0 (compatible; KaspiOffersInsight/1.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36',
      locale: 'ru-RU',
    })
    // Set city cookie
    await ctx.addCookies([
      {
        name: 'kaspi_city_id',
        value: String(cityId),
        domain: '.kaspi.kz',
        path: '/',
        httpOnly: false,
        secure: true,
        sameSite: 'Lax',
      },
    ])
    return await fn(ctx, browser)
  } finally {
    await browser.close()
  }
}

function productPageUrlFromId(productId: string): string {
  // Kaspi accepts any slug as long as the trailing -<id> exists
  return `https://kaspi.kz/shop/p/p-${productId}/`
}

function masterPageUrlFromId(masterProductId: string): string {
  return `https://kaspi.kz/shop/p/m-${masterProductId}/`
}

function blockHeavyResources(page: Page) {
  const blockedTypes = new Set(['image', 'media', 'font', 'stylesheet'])
  page.route('**/*', async (route) => {
    try {
      const req = route.request()
      if (blockedTypes.has(req.resourceType())) {
        return route.abort()
      }
      return route.continue()
    } catch {
      try { await route.continue() } catch { /* ignore */ }
    }
  })
}

async function collectOffersFromNetwork(page: Page): Promise<Seller[]> {
  const sellers: Seller[] = []

  page.on('response', async (res) => {
    try {
      const url = res.url()
      const ct = res.headers()['content-type'] || ''
      if (!ct.includes('application/json')) return
      // Heuristic: URLs that likely contain offer data
      if (!/(offer|offers|seller|sellers|price)/i.test(url)) return
      const json = await res.json().catch(() => null)
      if (!json) return

      const push = (o: any) => {
        sellers.push({
          name: String(o?.merchantName || o?.sellerName || 'Unknown'),
          price: Number(o?.price || o?.minPrice || o?.amount || 0),
          deliveryDate: String(o?.deliveryDate || o?.deliveryTime || o?.delivery || ''),
        })
      }

      if (Array.isArray(json)) json.forEach(push)
      else if (Array.isArray(json?.offers)) json.offers.forEach(push)
      else if (Array.isArray(json?.data)) json.data.forEach(push)
    } catch {
      // ignore parse errors
    }
  })

  return sellers
}

async function discoverVariantsFromDom(page: Page): Promise<{ productId: string; label: string }[]> {
  // Try to read a global JSON object
  const viaEval = await page.evaluate(() => {
    const out: { productId: string; label: string }[] = []
    try {
      // @ts-ignore
      const root = (window as any).__KASPI__
      const variants = root?.pageData?.variants || root?.variants
      if (Array.isArray(variants)) {
        for (const v of variants) {
          const id = String(v?.id ?? v?.productId ?? '')
          if (id) out.push({ productId: id, label: String(v?.label ?? v?.name ?? '') })
        }
      }
    } catch {}
    // If empty, try to scan script tags
    if (out.length === 0) {
      try {
        const scripts = Array.from(document.querySelectorAll('script'))
        for (const s of scripts) {
          const t = s.textContent || ''
          if (!t.includes('productId')) continue
          const ids = Array.from(t.matchAll(/"productId"\s*:\s*"?(\d+)"?/g)).map((m) => m[1])
          const labels = Array.from(t.matchAll(/"label"\s*:\s*"([^"]+)"/g)).map((m) => m[1])
          if (ids.length) {
            for (let i = 0; i < ids.length; i++) {
              out.push({ productId: ids[i], label: labels[i] || `Variant ${i + 1}` })
            }
            break
          }
        }
      } catch {}
    }
    return out
  })
  // Deduplicate by productId
  const seen = new Set<string>()
  const uniq: { productId: string; label: string }[] = []
  for (const v of viaEval) {
    if (!seen.has(v.productId)) {
      seen.add(v.productId)
      uniq.push(v)
    }
  }
  return uniq
}

async function scrapeVariantPage(page: Page, productId: string): Promise<{ sellers: Seller[]; labelGuess?: string; productName?: string }> {
  page.setDefaultTimeout(SCRAPE_TIMEOUT_MS)
  blockHeavyResources(page)
  const sellers = await collectOffersFromNetwork(page)
  await page.goto(productPageUrlFromId(productId), { waitUntil: 'domcontentloaded', timeout: SCRAPE_TIMEOUT_MS })

  // Give some time for XHRs to fire and responses to arrive
  // Wait for network quiet or a short delay
  try {
    await page.waitForLoadState('networkidle', { timeout: 8_000 })
  } catch {}
  await page.waitForTimeout(1_000)

  // Fallback: try to extract sellers from DOM if network listener didn't catch anything
  const domSellers = await page.evaluate(() => {
    const rows: { name: string; price: number; deliveryDate: string }[] = []
    try {
      const textNodes = Array.from(document.querySelectorAll('[class*="merchant"], [class*="seller"], [data-merchant]'))
      // Heuristic extraction; site-specific selectors may vary
      for (const el of textNodes.slice(0, 100)) {
        const name = (el as HTMLElement).innerText?.trim()
        if (!name) continue
        const container = el.closest('tr') || el.parentElement
        const priceEl = container?.querySelector('[class*="price"], [data-price]') as HTMLElement | null
        const deliveryEl = container?.querySelector('[class*="delivery"], [data-delivery]') as HTMLElement | null
        const priceNum = Number((priceEl?.innerText || '').replace(/[^0-9.]/g, ''))
        const delivery = (deliveryEl?.innerText || '').trim()
        if (name) rows.push({ name, price: priceNum || 0, deliveryDate: delivery })
      }
    } catch {}
    return rows
  })

  if (sellers.length === 0 && domSellers.length > 0) {
    sellers.push(...domSellers)
  }

  const labelGuess = await page.evaluate(() => {
    try {
      const el = document.querySelector('[data-testid*="variant" i], [class*="variant" i] [class*="selected" i]') as HTMLElement | null
      return el?.innerText?.trim() || ''
    } catch { return '' }
  })

  const productName = await page.evaluate(() => {
    try {
      const h1 = document.querySelector('h1') as HTMLElement | null
      return (h1?.innerText?.trim()) || document.title
    } catch { return '' }
  })

  return { sellers, labelGuess: labelGuess || undefined, productName: productName || undefined }
}

async function retry<T>(fn: () => Promise<T>, isRetryableError?: (e: any) => boolean): Promise<T> {
  let attempt = 0
  let lastErr: any
  while (attempt < MAX_RETRIES) {
    try {
      return await fn()
    } catch (e: any) {
      lastErr = e
      const msg = String(e?.message || '')
      if (isRetryableError && !isRetryableError(e)) break
      // backoff 500ms, 1500ms
      const delay = 500 * (attempt + 1) ** 2
      await new Promise((r) => setTimeout(r, delay))
      attempt++
    }
  }
  throw lastErr
}

export async function scrapeAnalyze(masterProductId: string, cityId: string): Promise<AnalyzeResult> {
  const started = Date.now()
  const variants: Variant[] = []
  let productName: string = 'Unknown Product'

  await withBrowser(cityId, async (ctx) => {
    const page = await ctx.newPage()
    page.setDefaultTimeout(SCRAPE_TIMEOUT_MS)
    blockHeavyResources(page)

    // Navigate to master product page first
    await retry(async () => {
      await page.goto(masterPageUrlFromId(masterProductId), { waitUntil: 'domcontentloaded', timeout: SCRAPE_TIMEOUT_MS })
    })

    // Grab product name from the master page
    productName = (await page.evaluate(() => {
      try {
        const h1 = document.querySelector('h1') as HTMLElement | null
        return (h1?.innerText?.trim()) || document.title
      } catch { return '' }
    })) || productName

    // Discover variants via DOM/embedded JSON
    let discovered = await discoverVariantsFromDom(page)
    if (discovered.length === 0) {
      // fallback: treat master as a single variant
      discovered = [{ productId: masterProductId, label: 'Default' }]
    }

    // For each variant, scrape sellers (with cache and retries)
    for (let i = 0; i < discovered.length; i++) {
      const v = discovered[i]
      const cached = fromCached(v.productId)
      if (cached) {
        variants.push({
          productId: v.productId,
          label: cached.label || v.label || `Variant ${i + 1}`,
          sellersCount: cached.sellers.length,
          sellers: cached.sellers,
        })
        continue
      }

      const variantPage = await ctx.newPage()
      try {
        const { sellers, labelGuess } = await retry(
          async () => await scrapeVariantPage(variantPage, v.productId),
          (e) => /timeout|ECONN|net::/i.test(String(e?.message || ''))
        )
        rememberVariant(v.productId, sellers, labelGuess || v.label)
        variants.push({
          productId: v.productId,
          label: labelGuess || v.label || `Variant ${i + 1}`,
          sellersCount: sellers.length,
          sellers,
        })
      } catch {
        rememberVariant(v.productId, [], v.label)
        variants.push({ productId: v.productId, label: v.label || `Variant ${i + 1}`, sellersCount: 0, sellers: [] })
      } finally {
        await variantPage.close()
      }
    }

    await page.close()
  })

  const elapsedMs = Date.now() - started
  return {
    masterProductId,
    productName,
    cityId,
    variants,
    meta: { scrapedAt: new Date().toISOString(), source: 'kaspi.kz', notes: `elapsedMs=${elapsedMs}` },
  }
}


