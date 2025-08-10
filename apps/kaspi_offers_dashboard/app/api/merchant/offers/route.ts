import { NextResponse } from 'next/server'
import { mcFetch, getMerchantId } from '@/lib/kaspi/client'

type OfferRow = {
  sku: string
  productId: number
  name: string
  price: number
}

function pickArrayKey(obj: any): { key: string | null; arr: any[] } {
  const candidates = [
    'items',
    'content',
    'data.items',
    'data.content',
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

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url)
    const p = Number(searchParams.get('p') ?? '0')
    const l = Number(searchParams.get('l') ?? '50')
    const m = getMerchantId()

    const urlA = `/bff/offer-view/list?m=${m}&p=${p}&l=${l}&a=true&t=&c=&lowStock=false&notSpecifiedStock=false`
    const resA = await mcFetch(urlA)
    const textA = await resA.text()
    let jsonA: any
    try { jsonA = JSON.parse(textA) } catch { jsonA = textA }
    let picked = pickArrayKey(jsonA)

    // fallback
    if (!picked.arr.length) {
      const urlB = `/bff/offer-view/list?m=${m}&p=0&l=10&available=true&t=&c=&lowStock=false&notSpecifiedStock=false`
      const resB = await mcFetch(urlB)
      const textB = await resB.text()
      let jsonB: any
      try { jsonB = JSON.parse(textB) } catch { jsonB = textB }
      picked = pickArrayKey(jsonB)
    }

    const rows: OfferRow[] = picked.arr
      .map((it: any) => {
        const sku = it.merchantSku || it.sku || it.offerSku || it.s || it.id || ''
        const productId = Number(it.variantProductId ?? it.productId ?? it.variantId ?? 0)
        const name = it.name || it.title || it.productName || ''
        const price = Number(it.price ?? it.currentPrice ?? it.offerPrice ?? it.value ?? 0)
        return sku ? { sku, productId, name, price } : null
      })
      .filter(Boolean) as OfferRow[]

    if (!rows.length) {
      return NextResponse.json({ ok: true, items: [], debug: { tried: 2, pickedKey: picked.key, hints: ['/api/debug/merchant/list?raw=1'] } })
    }
    return NextResponse.json({ ok: true, items: rows })
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e?.message || e) }, { status: 500 })
  }
}


