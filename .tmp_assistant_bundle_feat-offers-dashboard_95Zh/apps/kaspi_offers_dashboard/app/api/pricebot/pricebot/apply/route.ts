import { NextResponse } from 'next/server'
import { defaultWriter } from '@/server/pricebot/adapter'

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const updates = Array.isArray(body?.updates) ? body.updates : []
    const dryRun = body?.dryRun !== false
    const res = await defaultWriter.applyPrices(updates, { dryRun })
    return NextResponse.json({ ok: res.ok, applied: res.applied, file: (res as any).file, errors: res.errors || [] })
  } catch (e:any) {
    return NextResponse.json({ ok:false, error:String(e?.message||e) }, { status: 500 })
  }
}


