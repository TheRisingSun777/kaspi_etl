import { NextResponse } from 'next/server'
import { mcFetch, getMerchantId } from '@/lib/kaspi/client'

type OfferRow = {
  sku: string
  productId: number
  name: string
  price: number
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url)
    const p = Number(searchParams.get('p') ?? '0')
    const l = Number(searchParams.get('l') ?? '50')
    const m = getMerchantId()

    const url = `/bff/offer-view/list?m=${m}&p=${p}&l=${l}&a=true&t=&c=&lowStock=false&notSpecifiedStock=false`
    const res = await mcFetch(url)
    const text = await res.text()
    let json: any = null
    try { json = JSON.parse(text) } catch { json = text }

    const items: any[] = Array.isArray(json?.items) ? json.items : Array.isArray(json) ? json : []
    const rows: OfferRow[] = items
      .map((it: any) => {
        const sku = it.merchantSku || it.sku || it.offerSku || it.id || ''
        const productId = Number(it.variantProductId || it.productId || it.variantId || 0)
        const name = it.name || it.title || it.productName || ''
        const price = Number(it.price || it.currentPrice || it.ourPrice || 0)
        return sku ? { sku, productId, name, price } : null
      })
      .filter(Boolean) as OfferRow[]

    return NextResponse.json({ ok: true, items: rows })
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e?.message || e) }, { status: 500 })
  }
}


