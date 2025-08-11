import { NextResponse } from 'next/server'
import { mcFetch, getMerchantId } from '@/lib/kaspi/client'

type OfferRow = {
  sku: string
  productId: number
  name: string
  price: number
  stock: number
  opponents?: number
  shopLink?: string
}

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

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url)
    const t0 = Date.now()
    const p = Number(searchParams.get('p') ?? '0')
    const l = Number(searchParams.get('l') ?? '50')
    const available = (searchParams.get('available') || '').toString() === '1'
    const m = getMerchantId()

    const urlA = available
      ? `/bff/offer-view/list?m=${m}&p=${p}&l=${l}&available=true&t=&c=&lowStock=false&notSpecifiedStock=false`
      : `/bff/offer-view/list?m=${m}&p=${p}&l=${l}&a=true&t=&c=&lowStock=false&notSpecifiedStock=false`
    let resA: Response
    try { resA = await mcFetch(urlA) } catch (e:any) {
      if (String(e?.message||'').includes('401')) {
        return NextResponse.json({ ok: false, error: 'AUTH_FAILED', hint: 'Try cookie auth. Some MC list endpoints do not accept API key.' }, { status: 401 })
      }
      throw e
    }
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
        let productId = Number(it.variantProductId ?? it.productId ?? it.variantId ?? 0)
        const shopLink: string | undefined = it.shopLink || it.productLink || it.link || undefined
        if ((!productId || Number.isNaN(productId)) && typeof shopLink === 'string') {
          const m = shopLink.match(/-(\d+)\/?$/)
          if (m) productId = Number(m[1])
        }
        const name = it.masterTitle || it.title || it.name || it.productName || ''
        const price = Number(it.price ?? it.currentPrice ?? it.offerPrice ?? it.value ?? 0)
        const stock = pickStock(it)
        const opponents = Number(it.sellersCount || it.opponents || 0)
        return sku ? { sku, productId, name, price, stock, opponents, shopLink } : null
      })
      .filter(Boolean) as OfferRow[]

    const ms = Date.now() - t0
    const headers = new Headers({ 'X-Perf-ms': String(ms) })
    if (!rows.length) {
      return new NextResponse(JSON.stringify({ ok: true, items: [], debug: { tried: 2, pickedKey: picked.key, hints: ['/api/debug/merchant/list?raw=1'] } }), { headers })
    }
    return new NextResponse(JSON.stringify({ ok: true, items: rows }), { headers })
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e?.message || e) }, { status: 500 })
  }
}

function pickStock(o: any): number {
  // Prefer nested precise counts first
  const av = o?.availabilities?.[0]
  const nested = ['stockCount','availableAmount','freeBalance','quantity','qty','available']
  if (av) {
    for (const k of nested) {
      const v = av[k]
      if (typeof v === 'number') return v
      if (typeof v === 'string' && v.trim() !== '') { const n = Number(v); if (Number.isFinite(n)) return n }
      if (typeof v === 'boolean') return v ? 1 : 0
    }
  }
  const keys = ['stock','stockTotal','availableAmount','freeBalance','quantity','qty','available']
  for (const k of keys) {
    const v = o?.[k]
    if (typeof v === 'number') return v
    if (typeof v === 'string' && v.trim() !== '') { const n = Number(v); if (Number.isFinite(n)) return n }
    if (typeof v === 'boolean') return v ? 1 : 0
  }
  return 0
}


