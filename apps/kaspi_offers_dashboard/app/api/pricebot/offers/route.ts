import { NextResponse } from 'next/server'
// import { readStore } from '@/server/db/pricebot.store'
import { getSettings } from '@/server/db/pricebot.settings'
import { extractProductIdAndVariantFromSku } from '@/server/pricebot/sku'
import { readCookieForMerchant } from '@/lib/kaspi/mcCookieStore'
export const runtime = 'nodejs'

function pickArrayKey(obj: any): { key: string | null; arr: any[] } {
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
    if (Array.isArray(cur)) return { key, arr: cur }
  }
  return { key: null, arr: [] }
}

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url)
    const merchantId = String(searchParams.get('merchantId') || searchParams.get('storeId') || process.env.KASPI_MERCHANT_ID || '')
    const q = String(searchParams.get('q') || '')
    const cookie = readCookieForMerchant(merchantId) || process.env.KASPI_MERCHANT_COOKIE || process.env.KASPI_MERCHANT_COOKIES || ''
    const base = process.env.KASPI_MERCHANT_API_BASE || 'https://mc.shop.kaspi.kz'
    const urlA = `${base}/bff/offer-view/list?m=${merchantId}&p=0&l=100&a=true&t=${encodeURIComponent(q)}&c=&lowStock=false&notSpecifiedStock=false`
    const resA = await fetch(urlA, { headers: {
      accept: 'application/json, text/plain, */*',
      origin: 'https://kaspi.kz', referer: 'https://kaspi.kz/', 'x-auth-version': '3',
      cookie
    }, cache: 'no-store' })
    const txtA = await resA.text()
    let jsA: any
    try { jsA = JSON.parse(txtA) } catch { jsA = txtA }
    let picked = pickArrayKey(jsA)

    if (!picked.arr.length) {
      const urlB = `${base}/bff/offer-view/list?m=${merchantId}&p=0&l=10&available=true&t=${encodeURIComponent(q)}&c=&lowStock=false&notSpecifiedStock=false`
      const resB = await fetch(urlB, { headers: { accept: 'application/json, text/plain, */*', origin: 'https://kaspi.kz', referer: 'https://kaspi.kz/', 'x-auth-version': '3', cookie }, cache: 'no-store' })
      const txtB = await resB.text()
      let jsB: any
      try { jsB = JSON.parse(txtB) } catch { jsB = txtB }
      picked = pickArrayKey(jsB)
    }

    // const stAll = readStore() // legacy settings merge (kept for now)
    const stV2 = getSettings(merchantId)
    const offers = picked.arr.map((o: any) => {
      const sku = o.merchantSku || o.sku || o.offerSku || o.id || ''
      const v2 = sku ? stV2.sku[sku] : undefined
      const stockKeys = ['stock','qty','quantity','availableAmount','freeBalance','available','stockTotal']
      const stock = (()=>{
        for (const k of stockKeys) {
          const v = (o as any)[k]
          if (typeof v === 'number') return v
          if (typeof v === 'boolean') return v ? 1 : 0
          if (typeof v === 'string' && v.trim() !== '') {
            const n = Number(v)
            if (Number.isFinite(n)) return n
          }
        }
        // nested paths
        const av = (o as any)?.availabilities?.[0]
        const nestedKeys = ['stockCount','available','qty','quantity','availableAmount','freeBalance']
        if (av) {
          for (const k of nestedKeys) {
            const v = (av as any)[k]
            if (typeof v === 'number') return v
          }
        }
        return 0
      })()
      let productId = Number(o.variantProductId ?? o.productId ?? o.variantId ?? o.id ?? 0)
      const shopLink: string | undefined = o.shopLink || o.productLink || o.link || undefined
      if ((!productId || Number.isNaN(productId)) && typeof shopLink === 'string') {
        const m = shopLink.match(/-(\d+)\/?$/)
        if (m) productId = Number(m[1])
      }
      if (!productId) {
        const e = extractProductIdAndVariantFromSku(sku)
        if (e.productId) productId = e.productId
      }
      const offerName = o.masterTitle || o.title || o.name || o.productName || ''
      const curPrice = Number(o.price ?? o.currentPrice ?? o.offerPrice ?? o.value ?? 0)
      const fixedSettings = v2
        ? {
            active: !!v2.active,
            min: Number(v2.minPrice || 0) || curPrice || 0,
            max: Number(v2.maxPrice || 0) || curPrice || 0,
            step: Number(v2.stepKzt || 1),
            interval: Number(v2.intervalMin || 5),
            ignoreSellers: Array.isArray(v2.ignoredOpponents) ? v2.ignoredOpponents : [],
          }
        : undefined
      return {
        name: offerName,
        sku: sku || null,
        productId,
        price: curPrice,
        stock,
        opponents: Number(o.sellersCount || o.opponents || 0),
        settings: fixedSettings,
      }
    })

    // ------------------------------------------------------------------
    // 1)  OPTIONAL seller scrape
    // ------------------------------------------------------------------
    const withOpponents = new URL(req.url).searchParams.get('withOpponents') === 'true'
    if (withOpponents) {
      const cityId = new URL(req.url).searchParams.get('cityId') || '710000000'
      const merchantId = new URL(req.url).searchParams.get('merchantId') || new URL(req.url).searchParams.get('storeId') || process.env.KASPI_MERCHANT_ID || ''
      const MAX_PAR = 5
      const queue: Promise<void>[] = []
      for (const it of offers as any[]) {
        const task = (async()=>{
          try {
            const qs = new URLSearchParams({ sku: String(it.sku||''), merchantId: String(merchantId||''), cityId: String(cityId) }).toString()
            const res = await fetch(`${new URL(req.url).origin}/api/pricebot/opponents?${qs}`)
            const js = await res.json().catch(()=>null)
            const sellers = Array.isArray(js?.items)? js.items : []
            it.sellers = sellers
            it.opponents = sellers.length
          } catch (err) {
            console.warn('[offers] opponents fetch failed for', it.sku, err)
            it.sellers = []
            it.opponents = 0
          }
        })()
        queue.push(task)
        if (queue.length >= MAX_PAR) {
          await Promise.race(queue)
          queue.splice(0, 1)
        }
      }
      await Promise.all(queue)
    }

    // ------------------------------------------------------------------
    // 2)  Return to caller
    // ------------------------------------------------------------------
    if (!offers.length) return NextResponse.json({ ok: true, items: [], debug: { tried: 2, pickedKey: picked.key, hints: ['/api/debug/merchant/list?raw=1'] } })
    return NextResponse.json({ ok: true, items: offers })
  } catch (e: any) {
    const msg = String(e?.message || '')
    const code = /MISSING_COOKIE/.test(msg)
      ? 'MISSING_COOKIE'
      : /401|403/.test(msg)
      ? 'AUTH_FAILED'
      : /404/.test(msg)
      ? 'BAD_API_BASE'
      : 'MERCHANT_ERR'
    return NextResponse.json({ error: code, detail: msg.slice(0, 300) }, { status: 502 })
  }
}