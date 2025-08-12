import { NextRequest, NextResponse } from 'next/server'
import { upsertRule, getRule } from '@/server/db/rules'

export async function PUT(req: NextRequest, { params }: { params: { variantId: string } }) {
  const id = params.variantId
  const json = await req.json().catch(()=>null) as any
  if (!json) return NextResponse.json({ error: 'invalid body' }, { status: 400 })
  const body = {
    variantId: id,
    minPrice: Number(json.minPrice||0),
    maxPrice: Number(json.maxPrice||0),
    step: Number(json.step||1),
    intervalMin: Number(json.intervalMin||5),
    active: Number(json.active?1:0),
  }
  if (!body.minPrice || !body.maxPrice) return NextResponse.json({ error: 'min/max required' }, { status: 400 })
  upsertRule(body)
  return NextResponse.json({ ok: true, rule: getRule(id) })
}


