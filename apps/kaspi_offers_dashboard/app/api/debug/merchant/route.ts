import { NextResponse } from 'next/server'
import { mcFetch, getMerchantId } from '@/lib/kaspi/client'

export const dynamic = 'force-dynamic'
export async function GET() {
  try {
    const m = getMerchantId()
    const res = await mcFetch(`/offers/api/v1/offer/count?m=${m}`)
    const data = await res.json()
    return NextResponse.json({ ok: true, status: 200, data })
  } catch (e:any) {
    const msg = (e && e.message) || 'unknown'
    const status = msg.includes('401') ? 401 : 500
    return NextResponse.json({ ok: false, status, error: msg }, { status })
  }
}