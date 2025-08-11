import { NextResponse } from 'next/server'
import { readMerchants, writeMerchants } from '@/server/merchants'

export const runtime = 'nodejs'

export function GET() {
  try {
    const list = readMerchants()
    const items = Array.isArray(list)
      ? Array.from(
          new Map(
            list
              .map((m: any) => ({ id: String(m.id || m.merchantId || ''), name: String(m.name || m.label || m.id || '') }))
              .filter((m) => !!m.id)
              .map((m) => [m.id, m])
          ).values()
        )
      : []
    return NextResponse.json({ ok: true, items })
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e?.message || e) }, { status: 500 })
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json().catch(() => ({}))
    if (!body || (!body.merchantId && !body.id)) {
      return NextResponse.json({ ok: false, code: 'bad_input', message: 'merchantId (or id) required' }, { status: 400 })
    }
    const merchantId = String(body.merchantId || body.id)
    const label = String(body.label || body.name || merchantId)
    const cityId = Number(body.cityId || 710000000)
    const cookieFile = body.cookieFile
    const apiKey = body.apiKey
    const list: any[] = readMerchants()
    const idx = list.findIndex((m: any) => String(m.merchantId || m.id) === merchantId)
    const next = { merchantId, label, cityId, cookieFile, apiKey }
    if (idx >= 0) list[idx] = next
    else list.push(next)
    writeMerchants(list)
    return NextResponse.json({ ok: true, items: list.map((m: any) => ({ id: String(m.merchantId || m.id), name: String(m.label || m.name || m.id) })) })
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e?.message || e) }, { status: 500 })
  }
}


