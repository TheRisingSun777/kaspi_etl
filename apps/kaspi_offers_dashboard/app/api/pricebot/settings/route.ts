import { NextResponse } from 'next/server'
import { getSettings as getV2, upsertSettings as upsertV2 } from '@/server/db/pricebot.settings'

export async function GET() {
  const url = new URL(globalThis.location?.href || 'http://localhost')
  const merchantId = url.searchParams.get('merchantId') || url.searchParams.get('storeId') || process.env.KASPI_MERCHANT_ID || ''
  const st = getV2(String(merchantId))
  return NextResponse.json({ ok: true, settings: st })
}

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const merchantId = String(body.merchantId || body.storeId || process.env.KASPI_MERCHANT_ID || '')
    const updates: Record<string, any> = body?.updates || body?.items || {}
    const globalIgnored: string[] | undefined = body?.globalIgnore || body?.global?.ignoreSellers
    const st = upsertV2(merchantId, updates, globalIgnored)
    return NextResponse.json({ ok: true, settings: st })
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e?.message || e) }, { status: 500 })
  }
}

function toNum(v: any): number | undefined { const n = Number(v); return Number.isFinite(n) ? n : undefined }

