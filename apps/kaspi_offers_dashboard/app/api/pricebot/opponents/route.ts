import { NextRequest, NextResponse } from 'next/server'
import fs from 'node:fs'
import path from 'node:path'

const OFFERS_API = 'https://kaspi.kz/yml/offer-view/offers'

function readKaspiCookie(merchantId?: string | null): string {
  try {
    if (!merchantId) return ''
    const p = path.join(process.cwd(), 'server', 'merchant', `${merchantId}.cookie.json`)
    const raw = fs.readFileSync(p, 'utf8')
    const j = JSON.parse(raw)
    return String(j.cookie || '')
  } catch {
    return ''
  }
}

function ensureCityCookie(raw: string, cityId: string): string {
  const base = String(raw || '')
  return /kaspi\.storefront\.cookie\.city=/.test(base)
    ? base
    : (base ? base + '; ' : '') + `kaspi.storefront.cookie.city=${cityId}`
}

async function fetchText(url: string, init: RequestInit): Promise<{ ok: boolean; status: number; text: string }> {
  const resp = await fetch(url, init)
  const text = await resp.text()
  if (!resp.ok) {
    console.error('[kaspi-fetch]', resp.status, url)
    console.info('[kaspi-body]', text.slice(0, 400))
  }
  return { ok: resp.ok, status: resp.status, text }
}

function tryParseJson(text: string): any | null {
  try { return JSON.parse(text) } catch { return null }
}

export async function GET(req: NextRequest) {
  const u = new URL(req.url)
  const productId = u.searchParams.get('productId') || ''
  const sku = u.searchParams.get('sku') || ''
  const cityId = u.searchParams.get('cityId') || '710000000'
  const merchantId = u.searchParams.get('merchantId') || ''

  if (!productId && !sku) {
    return NextResponse.json({ ok: false, error: 'Missing productId or sku' }, { status: 400 })
  }

  const envSf = process.env.KASPI_STOREFRONT_COOKIE || process.env.KASPI_STOREFRONT_COOKIES || ''
  const rawCookie = envSf || readKaspiCookie(merchantId)
  const cookieStr = ensureCityCookie(rawCookie || `locale=ru-RU; kaspi.storefront.cookie.city=${cityId}`, cityId)

  const referer = productId
    ? `https://kaspi.kz/shop/p/-${productId}/?c=${cityId}`
    : 'https://kaspi.kz/'

  const baseHeaders: Record<string, string> = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-KZ,ru;q=0.9,en;q=0.8',
    'Content-Type': 'application/json; charset=UTF-8',
    'Origin': 'https://kaspi.kz',
    'Referer': referer,
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'X-KS-City': cityId,
    'X-Requested-With': 'XMLHttpRequest',
    'Sec-Fetch-Site': 'same-site',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Dest': 'empty',
    'sec-ch-ua': '"Chromium";v="120", "Not=A?Brand";v="24"',
    'sec-ch-ua-platform': '"macOS"',
    'sec-ch-ua-mobile': '?0',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'Cookie': cookieStr,
  }

  // Build new payload
  let payload: any
  if (sku) {
    const entry: any = { sku: String(sku) }
    if (merchantId) entry.merchantId = String(merchantId)
    payload = { cityId: String(cityId), entries: [entry], options: ['PRICE'] }
  } else {
    payload = { cityId: String(cityId), productId: String(productId), options: ['PRICE'], page: 0, sort: 'DEFAULT', limit: 100 }
  }

  // 1) POST JSON with Content-Type
  let { ok, text } = await fetchText(OFFERS_API, { method: 'POST', headers: baseHeaders, body: JSON.stringify(payload) })
  let js = ok ? tryParseJson(text) : null
  if (!js && ok) {
    // Kaspi sometimes returns text/html error page; surface hint
    console.warn('[opponents] non-JSON OK body sample:', text.slice(0, 200))
  }

  // 2) Fallback: POST without Content-Type
  if (!js) {
    const h2 = { ...baseHeaders }
    delete (h2 as any)['Content-Type']
    const r2 = await fetchText(OFFERS_API, { method: 'POST', headers: h2, body: JSON.stringify(payload) })
    js = r2.ok ? tryParseJson(r2.text) : null
  }

  // 3) Fallback: GET with old qs (when productId is known)
  if (!js && productId) {
    const h3 = { ...baseHeaders }
    delete (h3 as any)['Content-Type']
    const qs = `?productId=${encodeURIComponent(productId)}&cityId=${encodeURIComponent(cityId)}&page=0&sort=DEFAULT&limit=100`
    const r3 = await fetchText(OFFERS_API + qs, { method: 'GET', headers: h3 })
    js = r3.ok ? tryParseJson(r3.text) : null
    if (!js && r3.ok) console.warn('[opponents:get] non-JSON OK body sample:', r3.text.slice(0, 200))
  }

  if (!js) {
    // 4) Last-resort fallback: scrape product page HTML and extract JSON-LD offers
    if (productId) {
      const htmlHeaders: Record<string, string> = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-KZ,ru;q=0.9,en;q=0.8',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
        'Cookie': cookieStr,
        'Referer': referer,
      }
      const url = `https://kaspi.kz/shop/p/-${productId}/?c=${cityId}`
      const page = await fetch(url, { headers: htmlHeaders, cache: 'no-store' }).then(r=>r.text()).catch(()=> '')
      if (page && /<script[^>]+application\/ld\+json/i.test(page)) {
        const scripts = Array.from(page.matchAll(/<script[^>]+application\/ld\+json"?[^>]*>([\s\S]*?)<\/script>/gi)).map(m=>m[1])
        let sellersFromLd: any[] = []
        for (const s of scripts) {
          try {
            const obj = JSON.parse(s.trim())
            const offers = Array.isArray(obj?.offers) ? obj.offers : (Array.isArray(obj?.offers?.offers) ? obj.offers.offers : [])
            if (Array.isArray(offers) && offers.length) {
              sellersFromLd = offers.map((o:any)=>({
                merchantId: String(o?.seller?.name || o?.seller || ''),
                merchantName: String(o?.seller?.name || o?.seller || ''),
                price: Number(o?.price || 0),
                isYou: false,
              }))
              if (sellersFromLd.length) break
            }
          } catch {}
        }
        if (sellersFromLd.length) {
          // Keep entries even without numeric merchantId so UI can at least show names/prices
          const list = sellersFromLd.filter(x=> x.merchantName && Number.isFinite(Number(x.price)))
          return NextResponse.json({ ok: true, items: list })
        }
      }
    }

    // 5) Optional: Playwright fallback (real browser context)
    if (process.env.PLAYWRIGHT_FALLBACK === '1' && productId) {
      try {
        const { chromium } = await import('playwright') as any
        const browser = await chromium.launch({ headless: true })
        const context = await browser.newContext({
          userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
        })
        const page = await context.newPage()
        await page.goto(`https://kaspi.kz/shop/p/-${productId}/?c=${cityId}`, { waitUntil: 'domcontentloaded', timeout: 15000 })
        const payloadForBrowser = payload
        const jsInBrowser = await page.evaluate(async (apiUrl, pld) => {
          const r = await fetch(apiUrl, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pld) })
          const t = await r.text()
          try { return JSON.parse(t) } catch { return null }
        }, OFFERS_API, payloadForBrowser)
        await browser.close()
        if (jsInBrowser && (Array.isArray(jsInBrowser) || Array.isArray(jsInBrowser?.items))) {
          js = jsInBrowser
        }
      } catch (e) {
        console.warn('[opponents:playwright] fallback failed', e)
      }
    }

    if (!js) return NextResponse.json({ ok: false, error: 'Kaspi returned no JSON (blocked?)' }, { status: 502 })
  }

  // Try to pick sellers array from multiple known shapes; else recursively search for likely arrays
  function pickArrayKey(obj: any): any[] {
    const candidates = [
      'items',
      'content',
      'data.items',
      'data.content',
      'data',
      'list',
      'offers',
      'offers.items',
      'results',
      'rows',
      'page.content',
    ]
    for (const key of candidates) {
      const parts = key.split('.')
      let cur: any = obj
      for (const p of parts) cur = cur?.[p]
      if (Array.isArray(cur)) return cur
    }
    return []
  }
  function isSellerLike(o: any): boolean {
    if (!o || typeof o !== 'object') return false
    const keys = Object.keys(o)
    const hasPrice = 'price' in o || 'offerPrice' in o || 'value' in o || (o?.prices && Array.isArray(o.prices))
    const hasMerchant = 'merchantId' in o || 'merchantUID' in o || 'sellerId' in o || 'merchantName' in o || 'seller' in o || 'name' in o
    return hasPrice && hasMerchant
  }
  function findFirstSellerArray(node: any): any[] {
    const seen = new Set<any>()
    const stack: any[] = [node]
    while (stack.length) {
      const cur = stack.shift()
      if (!cur || typeof cur !== 'object') continue
      if (seen.has(cur)) continue
      seen.add(cur)
      if (Array.isArray(cur)) {
        if (cur.some(isSellerLike)) return cur
        // explore nested arrays/objects too
        for (const v of cur) if (v && typeof v === 'object') stack.push(v)
        continue
      }
      for (const v of Object.values(cur)) stack.push(v)
    }
    return []
  }
  let offers: any[] = pickArrayKey(js)
  if (!offers.length) offers = findFirstSellerArray(js)
  const sellers = offers
    .map((o: any) => {
      const id = o.merchantId ?? o.merchantUID ?? o.id ?? o.sellerId ?? ''
      const name = o.merchantName ?? o.name ?? o.merchant ?? o.seller ?? ''
      let price = Number(o.price ?? o.offerPrice ?? o.value ?? 0)
      if (!Number.isFinite(price) && Array.isArray(o.prices)) {
        const p = o.prices.find((x:any)=> Number.isFinite(Number(x?.price)))
        if (p) price = Number(p.price)
      }
      return {
        merchantId: String(id || name || ''),
        merchantName: String(name || id || ''),
        price: Number.isFinite(price) ? price : 0,
        isYou: !!merchantId && (String(id || '') === String(merchantId)),
      }
    })
    .filter((s: any) => s.merchantId && s.merchantName)

  return NextResponse.json({ ok: true, items: sellers })
}