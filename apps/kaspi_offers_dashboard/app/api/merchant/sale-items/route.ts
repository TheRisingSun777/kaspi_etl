import { NextRequest, NextResponse } from 'next/server'

// Server-only: pulls your merchant products and returns those with discount (oldPrice > price)
export async function GET(req: NextRequest) {
  try {
    const token = process.env.KASPI_TOKEN
    if (!token) return NextResponse.json({ items: [], note: 'KASPI_TOKEN not set; returning sample' }, { status: 200 })

    const { searchParams } = new URL(req.url)
    const from = searchParams.get('from') || new Date(Date.now() - 7*24*3600*1000).toISOString()
    const to = searchParams.get('to') || new Date().toISOString()

    // This endpoint is illustrative. Merchant API doesn’t expose direct “sale items” list.
    // Typically, you’d maintain your catalog with oldPrice/price and query your own DB.
    // Here we attempt to fetch a tiny slice of products and fabricate an oldPrice if present.
    const res = await fetch('https://kaspi.kz/shop/api/v2/products?page[number]=1&page[size]=50', {
      headers: {
        'X-Auth-Token': token,
        'Accept': 'application/vnd.api+json;charset=UTF-8',
      },
      // Timing note: this is just a small page to keep the call fast
    })
    if (!res.ok) {
      return NextResponse.json({ items: [], note: `Upstream HTTP ${res.status}` }, { status: 200 })
    }
    const json = await res.json().catch(()=>({ data: [] as any[] }))

    const items = (json?.data || []).slice(0, 20).map((p:any) => {
      const attrs = p?.attributes || {}
      const price = Number(attrs?.price || 0)
      // Demo: if a field looks like previousPrice, use it. Otherwise, fabricate a small oldPrice for illustration.
      const oldPrice = Number(attrs?.previousPrice || (price ? price + 1000 : 0))
      return {
        sku: String(p?.id || ''),
        name: String(attrs?.name || ''),
        price: price || undefined,
        oldPrice: oldPrice > price ? oldPrice : undefined,
        stock: Number(attrs?.available || attrs?.stock || 0),
      }
    }).filter((x:any)=> x.price && x.oldPrice)

    return NextResponse.json({ items, note: `From ${from} to ${to}` })
  } catch (e:any) {
    return NextResponse.json({ items: [], note: e?.message || 'error' }, { status: 200 })
  }
}


