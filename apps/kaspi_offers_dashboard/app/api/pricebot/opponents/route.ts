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

  const rawCookie = readKaspiCookie(merchantId)
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
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'X-KS-City': cityId,
    'X-Requested-With': 'XMLHttpRequest',
    'Sec-Fetch-Site': 'same-site',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Dest': 'empty',
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
  }

  if (!js) {
    return NextResponse.json({ ok: false, error: 'Kaspi returned no JSON (blocked?)' }, { status: 502 })
  }

  // Try to pick sellers array from multiple known shapes
  function pickArrayKey(obj: any): any[] {
    const candidates = [
      'items',
      'content',
      'data.items',
      'data.content',
      'data',
      'list',
      'offers',
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
    return Array.isArray(obj) ? obj : []
  }
  const offers: any[] = pickArrayKey(js)
  const sellers = offers
    .map((o: any) => ({
      merchantId: String(o.merchantId ?? o.merchantUID ?? o.id ?? o.sellerId ?? ''),
      merchantName: o.merchantName ?? o.name ?? o.merchant ?? o.seller ?? '',
      price: Number(o.price ?? o.offerPrice ?? o.value ?? o.prices?.[0]?.price ?? 0),
      isYou: !!merchantId && (String(o.merchantId ?? o.merchantUID ?? o.id ?? o.sellerId ?? '') === String(merchantId)),
    }))
    .filter((s: any) => s.merchantId)

  return NextResponse.json({ ok: true, items: sellers })
}