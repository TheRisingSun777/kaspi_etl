import { NextRequest, NextResponse } from 'next/server'

const OFFERS_API = 'https://kaspi.kz/yml/offer-view/offers'

type KaspiSeller = {
  merchantId: number
  merchantName?: string
  price?: number
  [k: string]: unknown
}

export async function GET(req: NextRequest) {
  try {
    const url = new URL(req.url)
    const sku        = url.searchParams.get('sku') || ''
    const cityId     = url.searchParams.get('cityId') || '710000000'
    const merchantId = url.searchParams.get('merchantId') || ''
    const productId  = url.searchParams.get('productId') || ''

    if (!sku) {
      return NextResponse.json({ ok: false, error: 'Missing sku' }, { status: 400 })
    }

    // Build payload exactly like the browser request; omit merchantId if not provided
    const entries: any[] = merchantId
      ? [{ sku, merchantId: String(merchantId) }]
      : [{ sku }]

    const payload = {
      cityId: String(cityId),
      entries,
      options: ['PRICE'],
      zoneId: ['Magnum_ZONE5'],
    }

    const resp = await fetch(OFFERS_API, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json; charset=UTF-8',
        'Accept': 'application/json, text/*',
        'Origin': 'https://kaspi.kz',
        // A product-like referer helps pass CSRF checks; productId is fine even without slug
        'Referer': `https://kaspi.kz/shop/p/${productId || '0'}/?c=${cityId}`,
        'X-KS-City': String(cityId),
        // City cookie is required server-side
        'Cookie': `kaspiDeliveryGeo=${cityId}; kaspi.storefront.cookie.city=${cityId}`,
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
      },
      body: JSON.stringify(payload),
      redirect: 'follow',
    })

    const raw = await resp.text()

    if (!resp.ok) {
      console.error('[kaspi-fetch]', resp.status, OFFERS_API)
      console.info('[kaspi-body]', raw.slice(0, 400))
      return NextResponse.json({ error: `Kaspi returned ${resp.status}`, body: raw.slice(0, 400) }, { status: 502 })
    }

    let sellers: KaspiSeller[] = []
    try { sellers = JSON.parse(raw) as KaspiSeller[] } catch {}

    return NextResponse.json({ ok: true, items: Array.isArray(sellers) ? sellers : [] })
  } catch (err: any) {
    return NextResponse.json({ ok: false, error: err?.message || String(err) }, { status: 500 })
  }
}