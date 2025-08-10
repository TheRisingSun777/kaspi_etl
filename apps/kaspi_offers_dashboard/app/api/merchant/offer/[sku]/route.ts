import { NextResponse } from 'next/server'
import { mcFetch, getMerchantId } from '@/lib/kaspi/client'

export async function GET(_req: Request, { params }: { params: { sku: string } }) {
  const m = getMerchantId()
  const sku = decodeURIComponent(params.sku)
  const url = `/bff/offer-view/details?m=${m}&s=${encodeURIComponent(sku)}`
  const res = await mcFetch(url)
  const data = await res.json()

  const sellers = (data?.sellers || data?.offers || []).map((s: any) => ({
    name: s?.sellerName || s?.name || '',
    price: Number(s?.price || s?.value || 0),
    isBot: !!(s?.bot || s?.priceBot || false),
  }))

  return NextResponse.json({
    ok: true,
    product: data?.product || data?.model || null,
    sellers,
  })
}


