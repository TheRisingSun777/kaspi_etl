import { NextResponse } from 'next/server'
import { getOffersPage } from '@/lib/merchant/client'

export const dynamic = 'force-dynamic'
export async function GET() {
  try {
    const js = await getOffersPage(0, 5)
    const count = Array.isArray((js as any)?.items) ? (js as any).items.length : 0
    return NextResponse.json({ ok: true, items: count })
  } catch (e:any) {
    return NextResponse.json({ ok:false, error: String(e?.message||e) }, { status: 500 })
  }
}