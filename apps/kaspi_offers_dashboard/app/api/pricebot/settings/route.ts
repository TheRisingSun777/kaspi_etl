import { NextResponse } from 'next/server'
import { getSettings as getV2, upsertSettings as upsertV2 } from '@/server/db/pricebot.settings'

export async function GET(req: Request) {
  const url = new URL(req.url)
  const merchantId = url.searchParams.get('merchantId') || url.searchParams.get('storeId') || process.env.KASPI_MERCHANT_ID || ''
  const st = getV2(String(merchantId))
  return NextResponse.json({ ok: true, settings: st })
}

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const merchantId = String(body.merchantId || body.storeId || process.env.KASPI_MERCHANT_ID || '')
    const rawUpdates: Record<string, any> = body?.updates || body?.items || {}
    const updates: Record<string, any> = {}
    for (const [sku, patch] of Object.entries(rawUpdates)) {
      const p = patch as any
      updates[sku] = {
        // accept both v1 and v2 field names
        active: typeof p.active === 'boolean' ? p.active : undefined,
        minPrice: numOr(p.minPrice, p.min, p.min_price),
        maxPrice: numOr(p.maxPrice, p.max, p.max_price),
        stepKzt: numOr(p.stepKzt, p.step),
        intervalMin: numOr(p.intervalMin, p.interval),
        ignoredOpponents: Array.isArray(p.ignoredOpponents)
          ? p.ignoredOpponents
          : Array.isArray(p.ignoreSellers)
          ? p.ignoreSellers
          : undefined,
      }
    }
    const globalIgnored: string[] | undefined = body?.globalIgnore || body?.global?.ignoreSellers
    const st = upsertV2(merchantId, updates, globalIgnored)
    return NextResponse.json({ ok: true, settings: st })
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e?.message || e) }, { status: 500 })
  }
}

function numOr(...values: any[]): number | undefined {
  for (const v of values) {
    const n = Number(v)
    if (Number.isFinite(n)) return n
  }
  return undefined
}

