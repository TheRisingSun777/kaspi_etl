import { NextResponse } from 'next/server'
import { mcFetch, getMerchantId } from '@/lib/kaspi/client'
import { extractProductIdAndVariantFromSku } from '@/server/pricebot/sku'

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url)
    const sku = String(searchParams.get('sku') || '')
    if (!sku) return NextResponse.json({ ok: false, error: 'MISSING_SKU' }, { status: 400 })
    const m = getMerchantId()
    const res = await mcFetch(`/bff/offer-view/details?m=${m}&s=${encodeURIComponent(sku)}`)
    const js = await res.json()
    // try nested availabilities first
    const av = js?.availabilities?.[0]
    let stock = 0
    const keys = ['stockCount','availableAmount','freeBalance','quantity','qty','available']
    if (av) {
      for (const k of keys) { const v = av[k]; if (typeof v === 'number') { stock = v; break } }
    }
    if (!stock) {
      for (const k of ['stock','stockTotal', ...keys]) { const v = (js as any)?.[k]; if (typeof v === 'number') { stock = v; break } }
    }
    const { productId } = extractProductIdAndVariantFromSku(sku)
    return NextResponse.json({ ok: true, sku, stock, productId })
  } catch (e:any) {
    void e
    return NextResponse.json({ ok: false, stock: 0 })
  }
}


