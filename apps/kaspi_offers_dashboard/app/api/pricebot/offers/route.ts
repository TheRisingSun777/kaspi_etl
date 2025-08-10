import { NextResponse } from 'next/server'
import { getMerchantId, mcFetch } from '@/lib/kaspi/client'
import { getItemSettingsOrDefault, readStore } from '@/server/db/pricebot.store'
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

export async function GET() {
  try {
    if (!process.env.KASPI_MERCHANT_API_BASE || !process.env.KASPI_MERCHANT_ID) {
      return NextResponse.json({ error: 'MISSING_ENV' }, { status: 500 })
    }

    const m = getMerchantId()
    const urlA = `/bff/offer-view/list?m=${m}&p=0&l=100&a=true&t=&c=&lowStock=false&notSpecifiedStock=false`
    const resA = await mcFetch(urlA)
    const txtA = await resA.text()
    let jsA: any
    try { jsA = JSON.parse(txtA) } catch { jsA = txtA }
    let picked = pickArrayKey(jsA)

    if (!picked.arr.length) {
      const urlB = `/bff/offer-view/list?m=${m}&p=0&l=10&available=true&t=&c=&lowStock=false&notSpecifiedStock=false`
      const resB = await mcFetch(urlB)
      const txtB = await resB.text()
      let jsB: any
      try { jsB = JSON.parse(txtB) } catch { jsB = txtB }
      picked = pickArrayKey(jsB)
    }

    const stAll = readStore()
    const offers = picked.arr.map((o: any) => {
      const sku = o.merchantSku || o.sku || o.offerSku || o.id || ''
      const settings = sku ? getItemSettingsOrDefault(sku) : undefined
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
      const offerName = o.masterTitle || o.title || o.name || o.productName || ''
      // default min/max to current price if settings are zeros
      const minDefault = settings && (!settings.min || settings.min===0) ? Number(o.price ?? o.currentPrice ?? o.offerPrice ?? o.value ?? 0) : settings?.min
      const maxDefault = settings && (!settings.max || settings.max===0) ? Number(o.price ?? o.currentPrice ?? o.offerPrice ?? o.value ?? 0) : settings?.max
      const fixedSettings = settings ? { ...settings, min: Number(minDefault||0), max: Number(maxDefault||0) } : undefined
      return {
        name: offerName,
        sku: sku || null,
        productId,
        price: Number(o.price ?? o.currentPrice ?? o.offerPrice ?? o.value ?? 0),
        stock,
        opponents: Number(o.sellersCount || o.opponents || 0),
        settings: fixedSettings,
      }
    })

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