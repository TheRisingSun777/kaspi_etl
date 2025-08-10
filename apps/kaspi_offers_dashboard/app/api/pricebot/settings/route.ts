import { NextResponse } from 'next/server'
import { readStore, upsertItemsBatch, updateGlobal, upsertItemIgnoreSeller } from '@/server/db/pricebot.store'

export async function GET() {
  const st = readStore()
  return NextResponse.json({ ok: true, settings: st })
}

export async function POST(req: Request) {
  try {
    const body = await req.json()
    if (body?.global) {
      const st = updateGlobal({ cityId: body.global.cityId, ignoreSellers: body.global.ignoreSellers })
      return NextResponse.json({ ok: true, settings: st })
    }
    if (body?.items && typeof body.items === 'object') {
      const st = upsertItemsBatch(body.items)
      return NextResponse.json({ ok: true, settings: st })
    }
    if (body?.toggleIgnore && body?.sku && body?.merchantId) {
      const s = upsertItemIgnoreSeller(String(body.sku), String(body.merchantId), !!body.ignore)
      return NextResponse.json({ ok: true, sku: body.sku, settings: s })
    }
    return NextResponse.json({ ok: false, error: 'BAD_BODY' }, { status: 400 })
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e?.message || e) }, { status: 500 })
  }
}

function toNum(v: any): number | undefined { const n = Number(v); return Number.isFinite(n) ? n : undefined }

