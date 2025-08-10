import { NextResponse } from 'next/server'
import { chromium } from 'playwright'
import { extractProductIdAndVariantFromSku } from '@/server/pricebot/sku'

const cache = new Map<string, { expires: number; data: any[] }>()

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url)
    let productId = String(searchParams.get('productId') || '')
    const sku = searchParams.get('sku') || ''
    const cityId = String(searchParams.get('cityId') || process.env.DEFAULT_CITY_ID || '710000000')
    if (!productId && sku) {
      const e = extractProductIdAndVariantFromSku(sku)
      if (e.productId) productId = String(e.productId)
    }
    if (!productId) return NextResponse.json({ ok: true, items: [] })

    const ck = `${productId}:${cityId}`
    const now = Date.now()
    const hit = cache.get(ck)
    if (hit && hit.expires > now) return NextResponse.json({ ok: true, items: hit.data })
    if (!productId) return NextResponse.json({ ok: true, sellers: [] })

    // First attempt: Kaspi JSON endpoint
    const jsonUrl = `https://kaspi.kz/yml/offer-view/offers?productId=${encodeURIComponent(productId)}&cityId=${encodeURIComponent(cityId)}`
    try {
      const res = await fetch(jsonUrl, { headers: { accept: 'application/json, text/plain, */*' }, cache: 'no-store' })
      if (res.ok) {
        const js = await res.json().catch(()=>null)
        const arr: any[] = Array.isArray(js?.data) ? js.data : Array.isArray(js?.offers) ? js.offers : Array.isArray(js) ? js : []
        if (arr.length) {
          const sellers = arr.map((r:any)=>({
            merchantUID: String(r.merchantId || r.merchantUID || r.sellerId || ''),
            merchantName: String(r.merchantName || r.sellerName || ''),
            price: Number(r.price || r.minPrice || r.priceBase || 0),
            isOurStore: String(r.merchantId || r.merchantUID || '') === String(process.env.KASPI_MERCHANT_ID || ''),
          })).filter(s=>s.price>0)
          sellers.sort((a,b)=>a.price-b.price)
          cache.set(ck, { expires: now + 3*60*1000, data: sellers })
          return NextResponse.json({ ok: true, items: sellers })
        }
      }
    } catch {}

    // Scraper fallback only if allowed
    if (process.env.ENABLE_SCRAPE !== '1') return NextResponse.json({ ok: true, sellers: [] })

    const browser = await chromium.launch({ headless: process.env.PW_HEADLESS !== '0' })
    const context = await browser.newContext()
    const page = await context.newPage()
    await page.goto(`https://kaspi.kz/shop/p/-${productId}/?c=${cityId}`, { waitUntil: 'domcontentloaded', timeout: 25000 })
    const rows = page.locator('.sellers-table tr, .merchant-list__item, .sellers-list__item')
    const sellers = await rows.evaluateAll((els: Element[])=>{
      const out: any[] = []
      for (const el of els) {
        const root = el as HTMLElement
        const name = (root.querySelector('.sellers-table__merchant-name') as HTMLElement)?.textContent?.trim() || ''
        const mId = (root.querySelector('[data-merchant-id]') as HTMLElement)?.getAttribute('data-merchant-id') || ''
        const priceTxt = (root.querySelector('.sellers-table__price-cell-text') as HTMLElement)?.textContent || ''
        const price = Number((priceTxt.match(/\d[\d\s]+/)?.[0]||'').replace(/\s/g,''))
        if (name && price>0) out.push({ merchantUID: mId, merchantName: name, price })
      }
      return out
    })
    await browser.close()
    sellers.sort((a:any,b:any)=>a.price-b.price)
    for (const s of sellers) s.isOurStore = String(s.merchantUID) === String(process.env.KASPI_MERCHANT_ID || '')
    cache.set(ck, { expires: now + 3*60*1000, data: sellers })
    return NextResponse.json({ ok: true, items: sellers })
  } catch (e:any) {
    return NextResponse.json({ ok: true, items: [] })
  }
}


